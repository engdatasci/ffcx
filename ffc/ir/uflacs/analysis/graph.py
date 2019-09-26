# -*- coding: utf-8 -*-
# Copyright (C) 2011-2017 Martin Sandve Alnæs
#
# This file is part of FFC (https://www.fenicsproject.org)
#
# SPDX-License-Identifier:    LGPL-3.0-or-later
"""Linearized data structure for the computational graph."""

import logging

import numpy

import ufl
from ffc.ir.uflacs.analysis.modified_terminals import is_scalar_modified_terminal, is_modified_terminal
from ffc.ir.uflacs.analysis.reconstruct import reconstruct
from ffc.ir.uflacs.analysis.valuenumbering import ValueNumberer

from ffc.ir.uflacs.analysis.visualise import visualise

logger = logging.getLogger(__name__)


class ExpressionGraph(object):
    """A directed multi-edge graph.
    ExpressionGraph allows multiple edges between the same nodes,
    and respects the insertion order of nodes and edges."""

    def __init__(self):

        # Data structures for directed multi-edge graph
        self.nodes = {}
        self.out_edges = {}
        self.in_edges = {}

    def number_of_nodes(self):
        return len(self.nodes)

    def add_node(self, key, **kwargs):
        """Add a node with optional properties."""
        self.nodes[key] = kwargs
        self.out_edges[key] = []
        self.in_edges[key] = []

    def add_edge(self, node1, node2):
        """Add a directed edge from node1 to node2."""
        if node1 not in self.nodes or node2 not in self.nodes:
            raise KeyError("Adding edge to unknown node")

        self.out_edges[node1] += [node2]
        self.in_edges[node2] += [node1]


def build_graph_vertices(expression, skip=(), skip_terminal_modifiers=False):
    # Count unique expression nodes

    G = ExpressionGraph()

    G.e2i = _count_nodes_with_unique_post_traversal(expression, skip, skip_terminal_modifiers)

    # Invert the map to get index->expression
    GV = sorted(G.e2i, key=G.e2i.get)

    # Add nodes to 'new' graph structure
    for i, v in enumerate(GV):
        G.add_node(i, expression=v)

    # Get vertex index representing input expression root
    V_target = G.e2i[expression]
    G.nodes[V_target]['target'] = True

    return G


def build_scalar_graph(expression):
    """Build list representation of expression graph covering the given expressions."""

    # Populate with vertices
    # Skip multiindices, these are not needed for numbering the symbols
    G = build_graph_vertices(expression, skip=(ufl.classes.MultiIndex,))

    # Build more fine grained computational graph of scalar subexpressions
    scalar_expression = rebuild_with_scalar_subexpressions(G)

    # Build new list representation of graph where all
    # vertices of V represent single scalar operations
    G = build_graph_vertices(scalar_expression, skip_terminal_modifiers=True)

    # Compute graph edges
    V_deps = []
    for i, v in G.nodes.items():
        expr = v['expression']
        if expr._ufl_is_terminal_ or (expr._ufl_is_terminal_modifier_ and expr.ufl_free_indices == ()):
            V_deps.append(())
        else:
            operand_indices = []
            for o in expr.ufl_operands:
                operand_indices.append(G.e2i[o])
            V_deps.append(operand_indices)

    for i, edges in enumerate(V_deps):
        for j in edges:
            G.add_edge(i, j)

    return G


def rebuild_with_scalar_subexpressions(G):
    """Build a new expression2index mapping where each subexpression is scalar valued.

    Input:
    - G.e2i
    - G.V
    - G.V_symbols
    - G.total_unique_symbols

    Output:
    - NV   - Array with reverse mapping from index to expression
    - nvs  - Tuple of ne2i indices corresponding to the last vertex of G.V
    """

    # Compute symbols over graph and rebuild scalar expression
    value_numberer = ValueNumberer(G)
    V_symbols = value_numberer.compute_symbols()
    total_unique_symbols = value_numberer.symbol_count

    # Array to store the scalar subexpression in for each symbol
    W = numpy.empty(total_unique_symbols, dtype=object)

    # Iterate over each graph node in order
    for i, v in G.nodes.items():
        expr = v['expression']
        # Find symbols of v components
        vs = V_symbols[i]

        # Skip if there's nothing new here (should be the case for indexing types)
        if all(W[s] is not None for s in vs):
            continue

        if is_modified_terminal(expr):
            sh = expr.ufl_shape
            if sh:
                # Store each terminal expression component. We may not
                # actually need all of these later, but that will be
                # optimized away.
                # Note: symmetries will be dealt with in the value numbering.
                ws = [expr[c] for c in ufl.permutation.compute_indices(sh)]
            else:
                # Store single modified terminal expression component
                if len(vs) != 1:
                    raise RuntimeError("Expecting single symbol for scalar valued modified terminal.")
                ws = [expr]
            # FIXME: Replace ws[:] with 0's if its table is empty
            # Possible redesign: loop over modified terminals only first,
            # then build tables for them, set W[s] = 0.0 for modified terminals with zero table,
            # then loop over non-(modified terminal)s to reconstruct expression.
        else:
            # Find symbols of operands
            sops = []
            for j, vop in enumerate(expr.ufl_operands):
                if isinstance(vop, ufl.classes.MultiIndex):
                    sops.append(())
                    continue
                # TODO: Build edge datastructure and use instead?
                # k = G.E[i][j]
                k = G.e2i[vop]
                sops.append(V_symbols[k])

            # Fetch reconstructed operand expressions
            wops = [tuple(W[k] for k in so) for so in sops]

            # Reconstruct scalar subexpressions of v
            ws = reconstruct(expr, wops)

            # Store all scalar subexpressions for v symbols
            if len(vs) != len(ws):
                raise RuntimeError("Expecting one symbol for each expression.")

        # Store each new scalar subexpression in W at the index of its symbol
        handled = set()
        for s, w in zip(vs, ws):
            if W[s] is None:
                W[s] = w
                handled.add(s)
            else:
                assert s in handled  # Result of symmetry! - but I think this never gets reached anyway (CNR)

    # Find symbols of final v from input graph
    vs = V_symbols[-1][0]
    scalar_expression = W[vs]
    return scalar_expression


def _count_nodes_with_unique_post_traversal(expr, skip=(), skip_terminal_modifiers=False):
    """Yields o for each node o in expr, child before parent.
    Never visits a node twice."""

    def getops(e):
        """Get a modifiable list of operands of e, optionally treating modified terminals as a unit."""
        if e._ufl_is_terminal_ or (skip_terminal_modifiers and e._ufl_is_terminal_modifier_ and e.ufl_free_indices == ()):
            return []
        else:
            return list(e.ufl_operands)

    e2i = {}
    stack = [(expr, getops(expr))]
    while stack:
        expr, ops = stack[-1]
        for i, o in enumerate(ops):
            if o is not None and o not in e2i:
                stack.append((o, getops(o)))
                ops[i] = None
                break
        else:
            if not isinstance(expr, (ufl.classes.Label,) + skip):
                count = len(e2i)
                e2i[expr] = count
            stack.pop()
    return e2i
