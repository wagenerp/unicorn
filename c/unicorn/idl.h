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

#ifndef UNICORN_IDL_H
#define UNICORN_IDL_H

#include "alpha4c/common/stringbuilder.h"
typedef struct uidl_t      uidl_t;
typedef struct uidl_node_t uidl_node_t;
typedef struct uidl_pair_t uidl_pair_t;

#define UIDL_LIMIT_UPPER 0x01
#define UIDL_LIMIT_LOWER 0x02
#define UIDL_LIMIT_RANGE 0x03

#define UIDL_COMPL_FLAT 0x01
#define UIDL_COMPL_ADHOC 0x02

uidl_t *uidl_new();
void    uidl_free(uidl_t *uidl);

void uidl_set_completion(uidl_t *uidl, uidl_node_t *node);
void uidl_set_completion_metadata(
	uidl_t *uidl, unsigned flags, const char *chStdout, const char *chStderr);
void uidl_set_definition(uidl_t *uidl, const char *key, uidl_node_t *node);

void uidl_to_json(uidl_t *node, sbuilder_t *sbuilder);

// todo: implement measurement and events

uidl_pair_t *uidl_pair(const char *key, uidl_node_t *node);

uidl_node_t *uidl_reference(const char *id);
uidl_node_t *uidl_string(const char *id, unsigned nOptions, ...);
uidl_node_t *uidl_float(const char *id, unsigned flags, double min, double max);
uidl_node_t *
uidl_integer(const char *id, unsigned flags, long long min, long long max);
uidl_node_t *
						 uidl_repeat(const char *id, uidl_node_t *subject, unsigned nEndings, ...);
uidl_node_t *uidl_sequence(const char *id, unsigned count, ...);
uidl_node_t *uidl_keyword(const char *id, unsigned count, ...);
void uidl_keyword_set(uidl_node_t *node, const char *ident, uidl_node_t *stmt);

void uidl_node_free(uidl_node_t *node);
void uidl_pair_free(uidl_pair_t *node);

void uidl_node_to_json(uidl_node_t *node, sbuilder_t *sbuilder);

#endif