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

import json
from . import autocomplete

import os

try:
	import jsonschema
	has_jsonschema = True
except ModuleNotFoundError:
	has_jsonschema = False

schema = None


def getSchema():
	global schema
	if schema is None:
		fn = os.path.join(os.path.dirname(os.path.realpath(__file__)),
		                  "idl-schema.json")
		with open(fn, "r") as f:
			schema = json.load(f)
	return schema


class IDL:
	def __init__(s,
	             topic,
	             completion,
	             flat=False,
	             stdout=None,
	             stderr=None,
	             result=None,
	             adHocChannels=False,
	             logging=None):
		s._topic = topic
		s._completion = completion
		s._flat = flat
		s._stdout = stdout
		s._stderr = stderr
		s._result = result
		s._adHocChannels = adHocChannels
		s._logging = logging

	@property
	def topic(s):
		return s._topic

	@property
	def completion(s):
		return s._completion

	@property
	def flat(s):
		return s._flat

	@property
	def stdout(s):
		return s._stdout

	@property
	def stderr(s):
		return s._stderr

	@property
	def result(s):
		return s._result

	@property
	def adHocChannels(s):
		return s._adHocChannels

	def toDict(s):
		res = {"completion": s._completion.toDict()}
		for k in ("flat", "stdout", "stderr", "logging"):
			v = getattr(s, f"_{k}")
			if v is not None:
				res[k] = v

		return res

	def toJSON(s):
		return json.dumps(s.toDict())

	@classmethod
	def FromJSON(cls, topic, obj, validate=True):
		args = dict(obj)
		if has_jsonschema and validate:
			jsonschema.validate(args, getSchema())
		args["completion"] = autocomplete.NodeFromJSON(args["completion"])
		autocomplete.ResolveReferences(args["completion"])
		return IDL(topic, **args)
