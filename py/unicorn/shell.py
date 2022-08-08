# Copyright 2022 Peter Wagener <mail@peterwagener.net>
#
# This file is part of the Unicorn framework.
#
# Unicorn is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# Unicorn is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# Unicorn. If not, see <https://www.gnu.org/licenses/>.

import sys
import os
import time
import shlex
import readline
import threading
from collections import namedtuple, defaultdict
import paho.mqtt.client as mqtt
import json
from . import autocomplete, idl
import traceback
import subprocess
import socks
import uuid
import socket
import jsonschema

topic_idl_map = dict()
lang = autocomplete.Keyword()
mqtt_client = None

mqtt_mid_pool = set()
mqtt_mid_pool_mutex = threading.Lock()
mqtt_mid_pool_cond = threading.Condition(mqtt_mid_pool_mutex)


def mqtt_mid_pool_add(mid):
	global mqtt_mid_pool
	with mqtt_mid_pool_mutex:
		mqtt_mid_pool.add(mid)
		mqtt_mid_pool_cond.notify_all()


def mqtt_mid_pool_wait(*mids):
	global mqtt_mid_pool
	with mqtt_mid_pool_mutex:
		for mid in mids:
			while mid not in mqtt_mid_pool:
				mqtt_mid_pool_cond.wait()
			mqtt_mid_pool.remove(mid)


def mid_add(mids, res):
	_, mid = res
	mids.add(mid)
	pass


class PrefixMode(defaultdict):
	def __init__(s,
	             topic=None,
	             include_head=False,
	             adhoc_channels=False,
	             stdout=None,
	             stderr=None,
	             result=None):
		defaultdict.__init__(s, lambda: PrefixMode())
		s.topic = topic
		s.include_head = include_head
		s.adhoc_channels = adhoc_channels
		s.stdout = stdout
		s.stderr = stderr
		s.result = result

	def clear(s):
		defaultdict.clear(s)
		s.topic = None
		s.include_head = False
		s.adhoc_channels = False
		s.stdout = None
		s.stderr = None
		s.result = None


prefix_modes = PrefixMode()


def build_lang(write_cache=True):
	global lang, prefix_modes
	lang = autocomplete.Keyword()
	prefix_modes.clear()
	for l in topic_idl_map.values():
		if l.flat:
			if not isinstance(l.completion, autocomplete.Keyword): continue
			lang._stmts.update(l.completion._stmts)
			for k in l.completion._stmts:
				prefix_modes[k].topic = l.topic
				prefix_modes[k].include_head = True
				prefix_modes[k].adhoc_channels = l.adHocChannels
				prefix_modes[k].stdout = l.stdout
				prefix_modes[k].stderr = l.stderr
				prefix_modes[k].result = l.result
		else:
			parent = lang
			prefix = prefix_modes
			keywords = l.topic.split("/")
			for kw in keywords[:-1]:
				if not kw in parent._stmts:
					parent._stmts[kw] = autocomplete.Keyword()
				parent = parent._stmts[kw]
				prefix = prefix[kw]
				if not isinstance(parent, autocomplete.Keyword):
					parent = None
					break
			if parent is None:
				continue
			parent._stmts[keywords[-1]] = l.completion
			prefix[keywords[-1]].topic = l.topic
			prefix[keywords[-1]].include_head = False
			prefix[keywords[-1]].adhoc_channels = l.adHocChannels
			prefix[keywords[-1]].stdout = l.stdout
			prefix[keywords[-1]].stderr = l.stderr
			prefix[keywords[-1]].result = l.result

	if write_cache and fn_cache is not None:
		with open(fn_cache, "w") as f:

			json.dump({k: (v.topic, v.toJSON()) for k, v in topic_idl_map.items()}, f)


def decode_command(cmdline):
	scanner = shlex.shlex(cmdline, posix=True, punctuation_chars=True)
	prefix = prefix_modes
	longest_prefix = None
	while True:
		pos = scanner.instream.tell()
		tok = scanner.get_token()
		if tok is None: break
		if not tok in prefix:
			break
		prefix = prefix[tok]
		if prefix.topic is not None:
			longest_prefix = (pos, scanner.instream.tell(), prefix)

	if longest_prefix is None: return
	pos_pre, pos_post, prefix = longest_prefix
	pos = pos_pre if prefix.include_head else pos_post
	param = cmdline[pos:].strip()

	if prefix.adhoc_channels:
		suffix = "/" + str(uuid.uuid4())
	else:
		suffix = ""

	return prefix, prefix.topic + suffix, param, suffix


def process_command(client, cmdline):
	raw = decode_command(cmdline)
	if raw is None: return

	prefix, topic, payload, suffix = raw

	if client is None:

		class Stopper:
			def __init__(s):
				s.stop = False

		stopper = Stopper()

		def on_connect(client, userdata, flags, rc):
			client.publish(topic, payload)

		def on_publish(client, userdata, mid):
			client.disconnect()
			userdata.stop = True

		client = mqtt.Client(userdata=stopper)

		if mqtt_proxy is not None:
			# set proxy ONLY after client build but after connect
			socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS4, *mqtt_proxy)
			socket.socket = socks.socksocket
		client.on_connect = on_connect
		client.on_publish = on_publish
		client.connect(mqtt_host, mqtt_port, 60)

		while not stopper.stop:
			client.loop()
	else:

		setResponseTopics(prefix.stdout, prefix.stderr, prefix.result, suffix)
		client.publish(topic, payload)


def load_cache(fn_cache):
	with open(fn_cache, "r") as f:
		try:
			entries = json.load(f).items()
		except json.JSONDecodeError:
			print("error decoding cache")
			return

	topic_idl_map = dict()
	for k, (topic, data) in entries:
		try:
			topic_idl_map[k] = idl.IDL.FromJSON(topic,
			                                    json.loads(data),
			                                    validate=False)
		except jsonschema.exceptions.ValidationError as e:
			# print(f"invalid IDL for topic {topic} (cache)")
			pass
	build_lang(write_cache=False)


def print_help(f):
	f.write("conglos [options] [command line] \n"
	        "options:\n"
	        "  -h|--help\n"
	        "    print this help text and exit normally\n")
	f.flush()


def completer(prefix, state):

	toks = autocomplete.TokenStream(readline.get_line_buffer(),
	                                readline.get_endidx())
	options = sorted(v for v in lang.complete(toks))
	if state < len(options):
		return options[state]

	return None


EV_INPUT = 0
EV_IDL_STDERR = 1
EV_IDL_STDOUT = 2
EV_TERMINATE = 3
EV_IDL_CONFIG = 4

ev_t = namedtuple("ev_t", "kind payload")
ev_mutex = threading.RLock()
ev_cond = threading.Condition(ev_mutex)
ev_queue = list()

topic_stdout = None
topic_stderr = None
topic_result = None


def setResponseTopics(stdout, stderr, result, suffix=""):
	if stdout is not None:
		stdout += suffix
	if stderr is not None:
		stderr += suffix
	if result is not None:
		result += suffix

	mids = set()

	global mqtt_client

	with ev_mutex:
		global topic_stdout, topic_stderr, topic_result
		if topic_stdout is not None:
			mqtt_client.unsubscribe(topic_stdout)
		if topic_stderr is not None:
			mqtt_client.unsubscribe(topic_stderr)
		if topic_result is not None:
			mqtt_client.unsubscribe(topic_result)
		topic_stdout = stdout
		topic_stderr = stderr
		topic_result = result
		if topic_stdout is not None:
			mid_add(mids, mqtt_client.subscribe(topic_stdout))
		if topic_stderr is not None:
			mid_add(mids, mqtt_client.subscribe(topic_stderr))
		if topic_result is not None:
			mid_add(mids, mqtt_client.subscribe(topic_result))

	mqtt_mid_pool_wait(*mids)


def ev_push(kind, payload):
	global ev_queue
	with ev_mutex:
		ev_queue.append(ev_t(kind, payload))
		ev_cond.notify_all()


def ev_pop():
	global ev_queue
	with ev_mutex:
		while len(ev_queue) < 1:
			ev_cond.wait()
		res = ev_queue[0]
		ev_queue = ev_queue[1:]
	return res


def handle_stdin():
	try:
		while True:
			ln = input("\x1b[s>")
			ev_push(EV_INPUT, ln)
	except EOFError as e:
		ev_push(EV_TERMINATE, None)


def println(ln):
	sys.stdout.write(
	  f"\x1b6n\x1b[u\x1b[0J\r{ln.rstrip()}\n\r\x1b[s>{readline.get_line_buffer()}"
	)
	# sys.stdout.write(f"\x1b[s\r{ln.rstrip()}\n\r\x1b[u")


def on_connect(client, userdata, flags, rc):
	client.subscribe("/unicorn/idl/#")


def on_message(client, userdata, msg):
	if msg.topic.startswith("/unicorn/idl/"):
		try:
			data = json.loads(msg.payload.decode())
		except (UnicodeDecodeError, json.JSONDecodeError) as e:
			return
		if not "completion" in data: return
		try:
			ev_push(EV_IDL_CONFIG, idl.IDL.FromJSON(msg.topic[13:], data))
		except jsonschema.exceptions.ValidationError as e:
			print(f"invalid IDL for topic {msg.topic[13:]}")
			print(json.dumps(data, indent='  '))
			print(e)
			return
		except Exception as e:
			print(msg.topic)
			traceback.print_exc()
			return

	elif msg.topic == topic_stdout:
		for ln in msg.payload.decode().rstrip().splitlines():
			println("[\x1b[32;1mout\x1b[30;0m]" + ln.rstrip())
	elif msg.topic == topic_stderr:
		for ln in msg.payload.decode().rstrip().splitlines():
			println("[\x1b[31;1merr\x1b[30;0m]" + ln.rstrip())
	elif msg.topic == topic_result:
		for ln in msg.payload.decode().rstrip().splitlines():
			println("[\x1b[35;1mret\x1b[30;0m]" + ln.rstrip())

		setResponseTopics(None, None, None)


def on_subscribe(client, userdata, mid, granted_qos):
	mqtt_mid_pool_add(mid)


def run(mqtt_host="mqtt",
        mqtt_port=1883,
        mqtt_proxy=None,
        fn_history=None,
        fn_cache=None):
	if fn_cache is not None and os.path.exists(fn_cache):
		load_cache(fn_cache)

	if True: # command-line argument handling

		command_line = list()

		fNonInteractive = False
		fPrintDMenuTree = False

		class clex(Exception):
			pass

		try:
			for i_arg, arg in enumerate(sys.argv[1:]):
				if arg in {"-h", "--help"}:
					print_help(sys.stdout)
					sys.exit(0)
				elif arg in {"--options"}:
					cmdline_str = " ".join([shlex.quote(v) for v in command_line]) + " "

					try:
						toks = autocomplete.TokenStream(cmdline_str, len(cmdline_str))
						print(" ".join(shlex.quote(v) for v in lang.complete(toks)))
					except SyntaxError as e:
						pass
					exit(0)
				elif arg in {"--dmenu-tree"}:
					fPrintDMenuTree = True
					pass
				elif arg == "--":
					command_line += sys.argv[i_arg + 2:]
					fNonInteractive = True
					break
				else:
					command_line.append(arg)
					fNonInteractive = True
		except clex as e:
			print_help(sys.stderr)
			sys.stderr.write("\x1b[31;1mError\x1b[30;0m: %s\n" % e)
			return 1

	if fNonInteractive:
		if len(command_line) > 0:
			process_command(None, " ".join([shlex.quote(v) for v in command_line]))
		return 0

	readline.set_completer(completer)
	readline.set_completer_delims(" \t")
	readline.parse_and_bind("tab: complete")

	readline.set_history_length(-1)
	if fn_history is not None and os.path.exists(fn_history):
		readline.read_history_file(fn_history)

	global mqtt_client
	mqtt_client = mqtt.Client()
	if mqtt_proxy is not None:
		# set proxy ONLY after client build but after connect
		socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS4, *mqtt_proxy)
		socket.socket = socks.socksocket
	mqtt_client.on_connect = on_connect
	mqtt_client.on_message = on_message
	mqtt_client.on_subscribe = on_subscribe
	mqtt_client.connect(mqtt_host, mqtt_port, 60)

	thrd_mqtt = threading.Thread(target=mqtt_client.loop_forever, daemon=True)
	thrd_mqtt.start()

	if fPrintDMenuTree:

		def printDMenuTree():
			def rec(node, handled=set(), cmdline=list()):
				if node in handled: return ""
				handled.add(node)
				res = ""
				if node is None or isinstance(node, autocomplete.Empty):
					raw = decode_command(shlex.join(cmdline))
					if raw is not None:
						prefix, topic, payload, suffix = raw
						res = ":output " + shlex.join(("mosquitto_pub", "-h", "mqtt", "-t",
						                               topic, "-m", payload)) + "\n"

				elif isinstance(node, autocomplete.Keyword):
					for k, v in node._stmts.items():
						sub = rec(v, handled, cmdline + [k])
						if sub is not None and len(sub) > 0:
							res += k + "\n" + sub
					if len(res) > 0 and len(cmdline) > 0:
						res = f":push\n{res}:pop\n"

				elif isinstance(node, autocomplete.Sequence):
					pass
				elif isinstance(node, autocomplete.Repeat):
					pass

				elif isinstance(node, (autocomplete.Number, autocomplete.String)):
					pass
				else:
					pass
				return res

			try:
				time.sleep(1)
				print(rec(lang))
			except Exception as e:
				print(e)
				traceback.print_exception(e)
			finally:
				ev_push(EV_TERMINATE, None)

		thrd_fin = threading.Thread(target=printDMenuTree, daemon=True)
		thrd_fin.start()
	else:
		thrd_stdin = threading.Thread(target=handle_stdin, daemon=True)
		thrd_stdin.start()

	import signal

	def interrupted(signum, frame):
		pass

	signal.signal(signal.SIGINT, interrupted)

	while True:
		ev = ev_pop()
		if ev.kind == EV_TERMINATE:
			break
		elif ev.kind == EV_INPUT:
			process_command(mqtt_client, ev.payload)
		elif ev.kind == EV_IDL_STDOUT:
			sys.stdout.write(ev.payload + "\n")
			sys.stdout.flush()
		elif ev.kind == EV_IDL_STDERR:
			sys.stderr.write(ev.payload + "\n")
			sys.stderr.flush()
		elif ev.kind == EV_IDL_CONFIG:
			topic_idl_map[ev.payload.topic] = ev.payload
			build_lang(write_cache=False)
	readline.write_history_file(fn_history)
