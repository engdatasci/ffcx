# -*- coding: utf-8 -*-
# Copyright (C) 2009-2018 Anders Logg and Garth N. Wells
#
# This file is part of FFC (https://www.fenicsproject.org)
#
# SPDX-License-Identifier:    LGPL-3.0-or-later
"""Compiler stage 5: Code formatting

This module implements the formatting of UFC code from a given
dictionary of generated C++ code for the body of each UFC function.

It relies on templates for UFC code available as part of the module
ufc_utils.

"""

import logging
import os
import pprint
import textwrap

from ffc import __version__ as FFC_VERSION
from ffc import FFCError
from ffc.backends.ufc import __version__ as UFC_VERSION
from ffc.parameters import compilation_relevant_parameters

logger = logging.getLogger(__name__)

FORMAT_TEMPLATE = {
    "ufc comment":
    """\
// This code conforms with the UFC specification version {ufc_version}
// and was automatically generated by FFC version {ffc_version}.
""",
    "dolfin comment":
    """\
// This code conforms with the UFC specification version {ufc_version}
// and was automatically generated by FFC version {ffc_version}.
//
// This code was generated with the option '-l dolfin' and
// contains DOLFIN-specific wrappers that depend on DOLFIN.
""",
    "header_h":
    """
#pragma once

""",
    "header_c":
    """
""",
}

c_extern_pre = """
#ifdef __cplusplus
extern "C" {
#endif
"""

c_extern_post = """
#ifdef __cplusplus
}
#endif
"""


def format_code(code, wrapper_code, prefix, parameters):
    """Format given code in UFC format. Returns two strings with header and source file contents."""

    logger.debug("Compiler stage 5: Formatting code")

    # Extract code
    (code_finite_elements, code_dofmaps, code_coordinate_mappings, code_integrals, code_forms,
     includes) = code

    # Generate code for comment at top of file
    code_h_pre = _generate_comment(parameters) + "\n"
    code_c_pre = _generate_comment(parameters) + "\n"

    # Generate code for header
    code_h_pre += FORMAT_TEMPLATE["header_h"]
    code_c_pre += FORMAT_TEMPLATE["header_c"]

    # Define ufc_scalar type before including ufc.h
    scalar_type = parameters.get("scalar_type")
    if scalar_type == "double complex":
        code_h_pre += "typedef double _Complex ufc_scalar;" + "\n"
        code_c_pre += "typedef double _Complex ufc_scalar;" + "\n"
    else:
        code_h_pre += "typedef double ufc_scalar;" + "\n"
        code_c_pre += "typedef double ufc_scalar;" + "\n"

    # Generate includes and add to preamble
    includes_h, includes_c = _generate_includes(includes, parameters)
    code_h_pre += includes_h
    code_c_pre += includes_c

    # Enclose header with 'extern "C"'
    code_h_pre += c_extern_pre
    code_h_post = c_extern_post

    # Add code for new finite_elements
    code_h = "".join([e[0] for e in code_finite_elements])
    code_c = "".join([e[1] for e in code_finite_elements])

    # Add code for dofmaps
    code_h += "".join([e[0] for e in code_dofmaps])
    code_c += "".join([e[1] for e in code_dofmaps])

    # Add code for code_coordinate mappings
    code_h += "".join([c[0] for c in code_coordinate_mappings])
    code_c += "".join([c[1] for c in code_coordinate_mappings])

    # Add code for integrals
    code_h += "".join([integral[0] for integral in code_integrals])
    code_c += "".join([integral[1] for integral in code_integrals])

    # Add code for form
    code_h += "".join([form[0] for form in code_forms])
    code_c += "".join([form[1] for form in code_forms])

    # Add wrappers
    if wrapper_code:
        code_h += wrapper_code[0]
        code_c += wrapper_code[1]

    # Add headers to body
    code_h = code_h_pre + code_h + code_h_post
    code_c = code_c_pre + code_c

    return code_h, code_c


def write_code(code_h, code_c, prefix, parameters):
    # Write file(s)
    _write_file(code_h, prefix, ".h", parameters)
    if code_c:
        _write_file(code_c, prefix, ".c", parameters)


def _write_file(output, prefix, postfix, parameters):
    """Write generated code to file."""
    filename = os.path.join(parameters["output_dir"], prefix + postfix)
    with open(filename, "w") as hfile:
        hfile.write(output)
    logger.info("Output written to " + filename + ".")


def _generate_comment(parameters):
    """Generate code for comment on top of file."""

    # Drop irrelevant parameters
    parameters = compilation_relevant_parameters(parameters)

    # Generate top level comment
    if parameters["format"] == "ufc":
        comment = FORMAT_TEMPLATE["ufc comment"].format(
            ffc_version=FFC_VERSION, ufc_version=UFC_VERSION)
    elif parameters["format"] == "dolfin":
        comment = FORMAT_TEMPLATE["dolfin comment"].format(
            ffc_version=FFC_VERSION, ufc_version=UFC_VERSION)
    else:
        raise FFCError("Unable to format code, unknown format \"{}\".".format(parameters["format"]))

    # Add parameter information
    comment += "//\n"
    comment += "// This code was generated with the following parameters:\n"
    comment += "//\n"
    comment += textwrap.indent(pprint.pformat(parameters), "//  ")
    comment += "\n"

    return comment


def _generate_includes(includes, parameters):

    default_h_includes = [
        "#include <ufc.h>",
    ]

    default_c_includes = [
        "#include <math.h>",  # This should really be set by the backend
        "#include <stdalign.h>",  # This should really be set by the backend
        "#include <stdbool.h>",  # This should really be set by the backend
        "#include <stdlib.h>",  # This should really be set by the backend
        "#include <string.h>",  # This should really be set by the backend
        "#include <ufc.h>",
    ]

    # external_includes = set(
    #     "#include <%s>" % inc for inc in parameters.get("external_includes", ()))

    s_h = set(default_h_includes) | includes
    s_c = set(default_c_includes)

    # s2 = external_includes - s

    includes_h = "\n".join(sorted(s_h)) + "\n" if s_h else ""
    includes_c = "\n".join(sorted(s_c)) + "\n" if s_c else ""

    scalar_type = parameters.get("scalar_type")
    if scalar_type == "double complex":
        includes_c += "#include<complex.h>" + "\n"

    return includes_h, includes_c
