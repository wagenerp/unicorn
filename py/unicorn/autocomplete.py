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

import shlex
import json
from collections import namedtuple
from collections.abc import Iterable

token_t = namedtuple("token_t", "code cursor")


class TokenStream:
	def __init__(s, code, loc):
		strings = shlex.split(code[:loc])
		if len(strings) < 1:
			s._tokens = [token_t("", 0)]
		else:
			if code[-1] in {" ", "\t"}:
				prefix = strings
				suffix = ""
			else:
				prefix = strings[:-1]
				suffix = strings[-1]
			s._tokens = [token_t(v, None) for v in prefix]
			s._tokens.append(token_t(suffix, len(suffix)))
		s._index = 0

	def next(s, peek=False):
		if s._index >= len(s._tokens):
			return token_t("", 0)
		res = s._tokens[s._index]
		if not peek:
			s._index += 1
		return res

	@property
	def remaining(s):
		return len(s._tokens) - s._index

	@property
	def eof(s):
		return s._index >= len(s._tokens)


class Node:
	def __init__(s, id=None):
		s._id = id

	@property
	def id(s):
		return s._id

	def complete(s, toks):
		raise NotImplementedError()

	def toDict(s):
		raise NotImplementedError()

	def toJSON(s):
		return json.dumps(s.toDict())

	def traverse(s, followReferences=False):
		yield s


class Reference(Node):
	def __init__(s, ref):
		Node.__init__(s)
		s._ref = ref
		s.node = None

	@property
	def ref(s):
		return s._ref

	def complete(s, toks):
		if False:
			yield None

		if s.node is not None:
			yield from s.node.complete(toks)

	def toDict(s):
		options = None
		if type(s._options) == set:
			options = list(sorted(s._options))
		return {"type": "string", "id": s._id, "options": options}

	@classmethod
	def FromJSON(s, obj):

		return Reference(ref=obj["ref"])

	def traverse(s, followReferences=False):
		yield s
		if followReferences and s.node is not None:
			yield from s.node.traverse(followReferences=followReferences)


class Keyword(Node):
	def __init__(s, id=None, **kwargs):
		Node.__init__(s, id)

		s._stmts = dict(kwargs)

	def complete(s, toks):
		tok = toks.next()
		if tok.cursor is None:
			if not tok.code in s._stmts:
				raise SyntaxError(
				  "expected one of %s" % (", ".join(sorted(s._stmts.keys()))))
			yield from s._stmts[tok.code].complete(toks)
		else:
			prefix = tok.code[:tok.cursor].lower()
			for kw in s._stmts:
				if kw.lower().startswith(prefix):
					yield kw

	def toDict(s):
		if hasattr(s, "_outputting"): return "null"
		setattr(s, "_outputting", True)
		res = {
		  "type": "keyword", "stmts": {k: v.toDict()
		                               for k, v in s._stmts.items()}
		}
		if s.id is not None: res["id"] = s.id
		delattr(s, "_outputting")
		return res

	@classmethod
	def FromJSON(s, obj):
		return Keyword(id=obj.get("id", None),
		               **{k: NodeFromJSON(v)
		                  for k, v in obj["stmts"].items()})

	def traverse(s, followReferences=False):
		yield s
		for child in s._stmts.values():
			yield from child.traverse(followReferences=followReferences)


class Sequence(Node):
	def __init__(s, *args, id=None):
		Node.__init__(s, id)

		s._stmts = args

	def complete(s, toks):
		for stmt in s._stmts:
			yield from stmt.complete(toks)
			done = toks.eof
			if done: break

	def toDict(s):
		if hasattr(s, "_outputting"): return "null"
		setattr(s, "_outputting", True)
		res = {"type": "sequence", "stmts": list([v.toDict() for v in s._stmts])}
		delattr(s, "_outputting")
		if s.id is not None: res["id"] = s.id
		return res

	@classmethod
	def FromJSON(s, obj):
		return Sequence(*[NodeFromJSON(v) for v in obj["stmts"]],
		                id=obj.get("id", None))

	def traverse(s, followReferences=False):
		yield s
		for child in s._stmts:
			yield from child.traverse(followReferences=followReferences)


class String(Node):
	def __init__(s, options=None, id=None):
		Node.__init__(s, id)
		s._options = options

	def complete(s, toks):
		if False:
			yield None
		tok = toks.next()
		if tok.cursor is None:
			if s._id is not None:
				setattr(toks, s._id, tok.code)
			return

		opts = set()
		if type(s._options) == set:
			opts = s._options
		elif callable(s._options):
			opts = s._options(toks)

		prefix = tok.code[:tok.cursor].lower()
		for opt in opts:
			if opt.lower().startswith(prefix):
				yield opt

	def toDict(s):
		options = None
		if type(s._options) == set:
			options = list(sorted(s._options))
		return {"type": "string", "id": s.id, "options": options}

	@classmethod
	def FromJSON(s, obj):
		options = None
		if "options" in obj and obj["options"] is not None:
			options = set(obj["options"])

		return String(options=options, id=obj.get("id", None))


class Number(Node):
	def __init__(s, integer=False, min=None, max=None, id=None):
		Node.__init__(s, id)
		s._integer = integer
		s._min = min
		s._max = max

	def complete(s, toks):
		if False:
			yield None
		tok = toks.next()
		if tok.cursor is None:
			if s._id is not None:
				setattr(toks, s._id, tok.code)
			return

		opts = set()
		if type(s._options) == set:
			opts = s._options
		elif callable(s._options):
			opts = s._options(toks)

		prefix = tok.code[:tok.cursor].lower()
		for opt in opts:
			if opt.lower().startswith(prefix):
				yield opt

	def toDict(s):
		return {
		  "type": "number", "id": s.id, "integer": s._integer, "min": s._min,
		  "max": s._max
		}

	@classmethod
	def FromJSON(s, obj):
		return Number(id=obj.get("id", None),
		              integer=obj.get("integer", False),
		              min=obj.get("min", None),
		              max=obj.get("max", None))


class Repeat(Node):
	def __init__(s, stmt, end=None, peekEnd=False, id=None):
		Node.__init__(s, id)
		s._stmt = stmt
		if end is None:
			s._end = None
		elif isinstance(end, str):
			s._end = str(end)
			s._end_set = {s._end}
		elif isinstance(end, Iterable):
			s._end = list(str(v) for v in end)
			s._end_set = set(s._end)
		else:
			raise TypeError(end)
		s._peekEnd = peekEnd

	def complete(s, toks):
		while True:
			if s._end is not None:
				tok = toks.next(peek=True)
				if tok.cursor is not None:
					prefix = tok.code[:tok.cursor].lower()
					for lit in sorted(s._end_set):
						if lit.lower().startswith(prefix):
							yield lit
				if tok.code in s._end_set:
					if not s._peekEnd: toks.next()
					break
			yield from s._stmt.complete(toks)
			done = toks.eof
			if done: break

	def toDict(s):
		if hasattr(s, "_outputting"): return "null"
		setattr(s, "_outputting", True)
		res = {
		  "type": "repeat", "stmt": s._stmt.toDict(), "end": s._end,
		  "peekEnd": s._peekEnd
		}
		if s.id is not None: res["id"] = s.id

		delattr(s, "_outputting")
		return res

	@classmethod
	def FromJSON(s, obj):
		return Repeat(NodeFromJSON(obj["stmt"]),
		              end=obj.get("end", None),
		              peekEnd=obj.get("peekEnd", False),
		              id=obj.get("id", None))

	def traverse(s, followReferences=False):
		yield s
		yield from s._stmt.traverse(followReferences=followReferences)


class Empty(Node):
	def __init__(s):
		Node.__init__(s)
		pass

	def complete(s, toks):
		if False: yield None
		pass

	def toDict(s):
		return None

	@classmethod
	def FromJSON(s, obj):
		return Empty()


object_classes = {
  "reference": Reference,
  "keyword": Keyword,
  "sequence": Sequence,
  "string": String,
  "number": Number,
  "repeat": Repeat,
  "empty": Empty,
}


def NodeFromJSON(obj):
	if obj is None: return Empty()
	clsid = obj["type"]
	cls = object_classes[clsid]
	return cls.FromJSON(obj)


def ResolveReferences(root: Node):
	id_node_map = dict()
	for node in root.traverse(followReferences=False):
		if node.id is not None:
			id_node_map[node.id] = node

	for node in root.traverse(followReferences=False):
		if not isinstance(node, Reference): continue
		if node.ref not in id_node_map:
			print(f"missing node reference in idl: {node.ref}")
			continue
		node.node = id_node_map[node.ref]
