/* Copyright 2022 Peter Wagener <mail@peterwagener.net>

This file is part of the Unicorn framework.

Unicorn is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

Unicorn is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
Unicorn. If not, see <https://www.gnu.org/licenses/>.
*/

#include "unicorn/idl.h"

#include "alpha4c/common/stringbuilder.h"
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct uidl_definition_t uidl_definition_t;
typedef struct uidl_definition_t {
	char *             key;
	uidl_node_t *      node;
	uidl_definition_t *next;
} uidl_definition_t;

typedef struct uidl_t {
	uidl_node_t *completion;
	uint32_t     flags;
	char *       chStdout;
	char *       chStderr;

	uidl_definition_t *definitions;

} uidl_t;

typedef enum uidl_type_t {
	Reference,
	String,
	Float,
	Integer,
	Repeat,
	Sequence,
	Keyword
} uidl_type_t;

typedef struct uidl_reference_t {
	char *targetID;
} uidl_reference_t;

typedef struct uidl_string_t {
	size_t nOptions;
	char **options;
} uidl_string_t;

typedef struct uidl_float_t {
	uint32_t flags;
	double   min, max;
} uidl_float_t;

typedef struct uidl_integer_t {
	uint32_t  flags;
	long long min, max;
} uidl_integer_t;

typedef struct uidl_repeat_t {
	uidl_node_t *subject;
	size_t       nEndings;
	char **      endings;
} uidl_repeat_t;

typedef struct uidl_sequence_t {
	size_t        nNodes;
	uidl_node_t **nodes;
} uidl_sequence_t;

typedef struct uidl_keyword_t {
	size_t        nPairs;
	uidl_pair_t **pairs;
} uidl_keyword_t;

typedef struct uidl_node_t {
	uidl_type_t type;
	char *      id;
	union {
		uidl_reference_t reference;
		uidl_string_t    string;
		uidl_float_t     number;
		uidl_integer_t   integer;
		uidl_repeat_t    repeat;
		uidl_sequence_t  sequence;
		uidl_keyword_t   keyword;
	};
} uidl_node_t;

typedef struct uidl_pair_t {
	char *       ident;
	uidl_node_t *node;
} uidl_pair_t;

uidl_t *uidl_new() {
	uidl_t *res      = (uidl_t *)malloc(sizeof(uidl_t));
	res->completion  = NULL;
	res->chStdout    = NULL;
	res->chStderr    = NULL;
	res->definitions = NULL;
	return res;
}
void uidl_free(uidl_t *uidl) {
	if (uidl->completion) { uidl_node_free(uidl->completion); }
	if (uidl->chStdout) free(uidl->chStdout);
	if (uidl->chStderr) free(uidl->chStderr);

	while (uidl->definitions) {
		uidl_definition_t *next = uidl->definitions->next;
		free(uidl->definitions->key);
		uidl_node_free(uidl->definitions->node);
		free(uidl->definitions);
		uidl->definitions = next;
	}

	free(uidl);
}

void uidl_set_completion(uidl_t *uidl, uidl_node_t *node) {
	if (uidl->completion) { uidl_node_free(uidl->completion); }

	uidl->completion = node;
}

void uidl_set_completion_metadata(
	uidl_t *uidl, unsigned flags, const char *chStdout, const char *chStderr) {
	if (uidl->chStdout) free(uidl->chStdout);
	if (uidl->chStderr) free(uidl->chStderr);

	uidl->flags    = flags;
	uidl->chStdout = chStdout ? strdup(chStdout) : NULL;
	uidl->chStderr = chStderr ? strdup(chStderr) : NULL;
}

void uidl_set_definition(uidl_t *uidl, const char *key, uidl_node_t *node) {
	uidl_definition_t **pdef = &uidl->definitions;

	while (*pdef) {
		if (strcmp((*pdef)->key, key) == 0) {
			uidl_node_free((**pdef).node);
			(**pdef).node = node;
			return;
		}
		pdef = &(**pdef).next;
	}

	*pdef         = (uidl_definition_t *)malloc(sizeof(uidl_definition_t));
	(*pdef)->key  = strdup(key);
	(*pdef)->node = node;
	(*pdef)->next = NULL;
}

void uidl_to_json(uidl_t *uidl, sbuilder_t *sb) {
	int first = 1;
#define HANDLEFIRST \
	if (first)        \
		first = 0;      \
	else              \
		sbuilder_append(sb, ",");

	sbuilder_append(sb, "{");

	if (uidl->flags & UIDL_COMPL_FLAT) {
		HANDLEFIRST
		sbuilder_append(sb, "\"flat\":true");
	}
	if (uidl->flags & UIDL_COMPL_ADHOC) {
		HANDLEFIRST
		sbuilder_append(sb, "\"adHocChannels\":true");
	}
	if (uidl->chStdout) {
		HANDLEFIRST
		sbuilder_sprintf(sb, "\"stdout\":\"%s\"", uidl->chStdout);
	}
	if (uidl->chStderr) {
		HANDLEFIRST
		sbuilder_sprintf(sb, "\"stderr\":\"%s\"", uidl->chStderr);
	}

	if (uidl->completion) {
		HANDLEFIRST
		sbuilder_append(sb, "\"completion\":");
		uidl_node_to_json(uidl->completion, sb);
	}

	if (uidl->definitions) {
		HANDLEFIRST
		sbuilder_append(sb, "\"definitions\":{");
		int first1 = 1;
		for (uidl_definition_t *def = uidl->definitions; def; def = def->next) {
			if (first1) {
				first1 = 0;
			} else {
				sbuilder_append(sb, ",");
			}
			sbuilder_sprintf(sb, "\"%s\":", def->key);
			uidl_node_to_json(def->node, sb);
		}
		sbuilder_append(sb, "}");
	}

#undef HANDLEFIRST

	sbuilder_append(sb, "}");
}

uidl_pair_t *uidl_pair(const char *key, uidl_node_t *node) {
	uidl_pair_t *res = (uidl_pair_t *)malloc(sizeof(uidl_pair_t));
	res->ident       = strdup(key);
	res->node        = node;
	return res;
}

uidl_node_t *uidl_reference(const char *id) {
	uidl_node_t *res        = (uidl_node_t *)malloc(sizeof(uidl_node_t));
	res->type               = Reference;
	res->reference.targetID = strdup(id);
	res->id                 = NULL;
	return res;
}
uidl_node_t *uidl_string(const char *id, unsigned nOptions, ...) {
	uidl_node_t *res     = (uidl_node_t *)malloc(sizeof(uidl_node_t));
	res->type            = String;
	res->id              = id ? strdup(id) : NULL;
	res->string.nOptions = nOptions;
	if (nOptions > 0) {
		res->string.options = (char **)malloc(sizeof(char *) * nOptions);
		va_list options;
		va_start(options, nOptions);
		for (unsigned i = 0; i < nOptions; i++) {
			res->string.options[i] = strdup(va_arg(options, const char *));
		}
		va_end(options);
	} else {
		res->string.options = NULL;
	}
	return res;
}
uidl_node_t *
uidl_float(const char *id, unsigned flags, double min, double max) {
	uidl_node_t *res  = (uidl_node_t *)malloc(sizeof(uidl_node_t));
	res->type         = Float;
	res->id           = id ? strdup(id) : NULL;
	res->number.flags = flags;
	res->number.min   = min;
	res->number.max   = max;
	return res;
}
uidl_node_t *
uidl_integer(const char *id, unsigned flags, long long min, long long max) {
	uidl_node_t *res   = (uidl_node_t *)malloc(sizeof(uidl_node_t));
	res->type          = Integer;
	res->id            = id ? strdup(id) : NULL;
	res->integer.flags = flags;
	res->integer.min   = min;
	res->integer.max   = max;
	return res;
}
uidl_node_t *
uidl_repeat(const char *id, uidl_node_t *subject, unsigned nEndings, ...) {
	uidl_node_t *res     = (uidl_node_t *)malloc(sizeof(uidl_node_t));
	res->type            = Repeat;
	res->id              = id ? strdup(id) : NULL;
	res->repeat.subject  = subject;
	res->repeat.nEndings = nEndings;
	if (nEndings > 0) {
		res->repeat.endings = (char **)malloc(sizeof(char *) * nEndings);
		va_list endings;
		va_start(endings, nEndings);
		for (unsigned i = 0; i < nEndings; i++) {
			res->repeat.endings[i] = strdup(va_arg(endings, const char *));
		}
		va_end(endings);
	} else {
		res->repeat.endings = NULL;
	}
	return res;
}
uidl_node_t *uidl_sequence(const char *id, unsigned count, ...) {
	uidl_node_t *res     = (uidl_node_t *)malloc(sizeof(uidl_node_t));
	res->type            = Sequence;
	res->id              = id ? strdup(id) : NULL;
	res->sequence.nNodes = count;
	if (count > 0) {
		res->sequence.nodes = (uidl_node_t **)malloc(sizeof(uidl_node_t *) * count);
		va_list nodes;
		va_start(nodes, count);
		for (unsigned i = 0; i < count; i++) {
			res->sequence.nodes[i] = va_arg(nodes, uidl_node_t *);
		}
		va_end(nodes);
	} else {
		res->sequence.nodes = NULL;
	}
	return res;
}
uidl_node_t *uidl_keyword(const char *id, unsigned count, ...) {
	uidl_node_t *res    = (uidl_node_t *)malloc(sizeof(uidl_node_t));
	res->type           = Keyword;
	res->id             = id ? strdup(id) : NULL;
	res->keyword.nPairs = count;
	if (count > 0) {
		res->keyword.pairs = (uidl_pair_t **)malloc(sizeof(uidl_pair_t *) * count);
		va_list pairs;
		va_start(pairs, count);
		for (unsigned i = 0; i < count; i++) {
			res->keyword.pairs[i] = va_arg(pairs, uidl_pair_t *);
		}
		va_end(pairs);
	} else {
		res->keyword.pairs = NULL;
	}
	return res;
}
void uidl_keyword_set(uidl_node_t *node, const char *ident, uidl_node_t *stmt) {
	if (!node->keyword.pairs) {
		node->keyword.nPairs   = 1;
		node->keyword.pairs    = (uidl_pair_t **)malloc(sizeof(uidl_pair_t *));
		node->keyword.pairs[0] = uidl_pair(ident, stmt);
	} else {
		for (size_t i = 0; i < node->keyword.nPairs; i++) {
			if (strcmp(node->keyword.pairs[i]->ident, ident) == 0) {
				uidl_node_free(node->keyword.pairs[i]->node);
				node->keyword.pairs[i]->node = stmt;
				return;
			}
		}
		{
			node->keyword.nPairs++;
			uidl_pair_t **pnew = (uidl_pair_t **)realloc(
				(void *)node->keyword.pairs,
				sizeof(uidl_pair_t *) * node->keyword.nPairs);
			if (pnew) node->keyword.pairs = pnew;
		}

		node->keyword.pairs[node->keyword.nPairs - 1] = uidl_pair(ident, stmt);
	}
}

void uidl_node_free(uidl_node_t *node) {
	if (!node) return;

	switch (node->type) {
		case Reference: free(node->reference.targetID); break;
		case String:

			if (node->string.nOptions > 0) {
				for (size_t i = 0; i < node->string.nOptions; i++)
					free(node->string.options[i]);
				free(node->string.options);
			}
			break;
		case Float: break;
		case Integer: break;
		case Repeat:
			uidl_node_free(node->repeat.subject);

			if (node->repeat.nEndings > 0) {
				for (size_t i = 0; i < node->repeat.nEndings; i++) {
					free(node->repeat.endings[i]);
				}
				free(node->repeat.endings);
			}
			break;
		case Sequence:

			if (node->sequence.nNodes > 0) {
				for (size_t i = 0; i < node->sequence.nNodes; i++) {
					uidl_node_free(node->sequence.nodes[i]);
				}
				free(node->sequence.nodes);
			}
			break;
		case Keyword:

			if (node->keyword.nPairs > 0) {
				for (size_t i = 0; i < node->keyword.nPairs; i++) {
					uidl_pair_free(node->keyword.pairs[i]);
				}
				free(node->keyword.pairs);
			}
			break;
	}

	if (node->id) free(node->id);
	free(node);
}

void uidl_pair_free(uidl_pair_t *pair) {
	free(pair->ident);
	uidl_node_free(pair->node);
	free(pair);
}

void uidl_node_to_json(uidl_node_t *node, sbuilder_t *sb) {
	if (!node) {
		sbuilder_append(sb, "null");
		return;
	}
	sbuilder_append(sb, "{");
	switch (node->type) {
		case Reference:
			sbuilder_sprintf(
				sb, "\"type\":\"reference\",\"ref\":\"%s\"", node->reference.targetID);
			break;

		case String:
			sbuilder_append(sb, "\"type\":\"string\",\"options\":[");
			if (node->string.options) {
				int first = 1;
				for (size_t i = 0; i < node->string.nOptions; i++) {
					if (first) {
						first = 0;
					} else {
						sbuilder_append(sb, ",");
					}
					sbuilder_sprintf(sb, "\"%s\"", node->string.options[i]);
				}
			}
			sbuilder_append(sb, "]");
			break;

		case Float:
			sbuilder_append(sb, "\"type\":\"number\",\"integer\":false");
			if (node->number.flags & UIDL_LIMIT_LOWER) {
				sbuilder_sprintf(sb, ",\"min\":%f", node->number.min);
			}
			if (node->number.flags & UIDL_LIMIT_UPPER) {
				sbuilder_sprintf(sb, ",\"max\":%f", node->number.max);
			}
			break;

		case Integer:
			sbuilder_append(sb, "\"type\":\"number\",\"integer\":true");
			if (node->integer.flags & UIDL_LIMIT_LOWER) {
				sbuilder_sprintf(sb, ",\"min\":%lli", node->integer.min);
			}
			if (node->integer.flags & UIDL_LIMIT_UPPER) {
				sbuilder_sprintf(sb, ",\"max\":%lli", node->integer.max);
			}
			break;

		case Repeat:
			sbuilder_append(sb, "\"type\":\"repeat\",\"stmt\":");
			uidl_node_to_json(node->repeat.subject, sb);

			if (node->repeat.nEndings == 1) {
				sbuilder_sprintf(sb, ",\"end\":\"%s\"", node->repeat.endings[0]);
			} else if (node->repeat.nEndings > 0) {
				sbuilder_append(sb, ",\"end\":[");
				int first = 1;
				for (size_t i = 0; i < node->repeat.nEndings; i++) {
					if (first) {
						first = 0;
					} else {
						sbuilder_append(sb, ",");
					}
					sbuilder_sprintf(sb, "\"%s\"", node->repeat.endings[i]);
				}
				sbuilder_append(sb, "]");
			}
			break;

		case Sequence: {
			sbuilder_append(sb, "\"type\":\"sequence\",\"stmts\":[");
			if (node->sequence.nodes) {
				int first = 1;
				for (size_t i = 0; i < node->sequence.nNodes; i++) {
					if (first) {
						first = 0;
					} else {
						sbuilder_append(sb, ",");
					}

					uidl_node_to_json(node->sequence.nodes[i], sb);
				}
			}
			sbuilder_append(sb, "]");
			break;
		}

		case Keyword: {
			sbuilder_append(sb, "\"type\":\"keyword\",\"stmts\":{");
			if (node->keyword.pairs) {
				int first = 1;
				for (size_t i = 0; i < node->keyword.nPairs; i++) {
					if (first) {
						first = 0;
					} else {
						sbuilder_append(sb, ",");
					}
					sbuilder_sprintf(sb, "\"%s\":", node->keyword.pairs[i]->ident);
					uidl_node_to_json(node->keyword.pairs[i]->node, sb);
				}
			}
			sbuilder_append(sb, "}");
			break;
		}
	}

	if (node->id) { sbuilder_sprintf(sb, ",\"id\":\"%s\"", node->id); }
	sbuilder_append(sb, "}");
}