__author__ = "Anders Logg (logg@tti-c.org)"
__date__ = "2005-05-16 -- 2005-09-20"
__copyright__ = "Copyright (c) 2005 Anders Logg"
__license__  = "GNU GPL Version 2"

# FIAT modules
from FIAT.dualbasis import *
from FIAT.shapes import *

# FFC modules
from declaration import *

# FIXME: Should not be DOLFIN-specific
format = { "point"     : lambda x : "points[%s]" % x,
           "affinemap" : lambda x : "map(%s)" % x,
           "component" : lambda i : "components[%s]" % i }

def compute_pointmap(element, local_offset, component_offset):
    "Compute pointmap for given element."

    # Get dual basis
    dual_basis = element.fiat_dual

    # Get points (temporary until we can handle other types of nodes)
    points = dual_basis.pts
    
    # Map point to reference element (different in FFC and FIAT)
    newpoints = []
    for point in points:
        newpoints += [tuple([0.5*(x + 1.0) for x in point])]
    points = newpoints

    # Get the number of vector components
    num_components = dual_basis.num_reps

    declarations = []

    # Iterate over the dofs and write coordinates
    dof = local_offset
    for component in range(num_components):
        for point in points:

            # Coordinate
            x = (", ".join(["%.15e" % x for x in point]))
            name = format["point"](dof)
            value = format["affinemap"](x)
            declarations += [Declaration(name, value)]
            
            dof += 1

    # Iterate over the dofs and write components
    dof = local_offset
    for component in range(num_components):
        for point in points:

            # Component
            name = format["component"](dof)
            value = "%d" % (component_offset + component)
            declarations += [Declaration(name, value)]
            
            dof += 1

    #for declaration in declarations:
    #    print declaration.name + " = " + declaration.value

    # Update local offset for next element (handles mixed elements)
    local_offset = dof

    # Update component offset for next element (handles mixed elements)
    component_offset += num_components

    return (declarations, local_offset, component_offset)

class PointMap:

    """A PointMap maps the coordinates of the degrees of freedom on
    the reference element to physical coordinates."""

    def __init__(self, elements):
        "Create PointMap."

        # Make sure we have a list of elements
        if not isinstance(elements, list):
            elements = [elements]

        # Iterate over elements (handles mixed elements)
        self.declarations = []
        local_offset = 0
        component_offset = 0
        for element in elements:
            (declarations, local_offset, component_offset) = compute_pointmap(element, local_offset, component_offset)
            self.declarations += declarations
