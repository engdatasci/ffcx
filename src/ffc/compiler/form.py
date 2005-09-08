__author__ = "Anders Logg (logg@tti-c.org)"
__date__ = "2004-09-27 -- 2005-09-05"
__copyright__ = "Copyright (c) 2004, 2005 Anders Logg"
__license__  = "GNU GPL Version 2"

# Python modules
import sys
from Numeric import *

# FFC common modules
from ffc.common.debug import *

# FFC format modules
sys.path.append("../../")
from ffc.format import dolfin
from ffc.format import latex

# FFC compiler modules
from index import *
from algebra import *
from reassign import *
from finiteelement import *
from elementtensor import *

class Form:

    """A Form represents a multi-linear form typically appearing in
    the variational formulation of partial differential equation.
    
    A Form holds the following data:

        sum     - a Sum representing the multi-linear form
        name    - a string, the name of the multi-linear form

    The following data is generated by the compiler:

        AKi        - interior ElementTensor
        AKb        - boundary ElementTensor
        rank       - primary rank of the multi-linear form
        dims       - list of primary dimensions
        indices    - list of primary indices
        nfunctions - number of functions (coefficients)
        nconstants - number of constants
        test       - FiniteElement defining the test space
        trial      - FiniteElement defining the trial space
        elements   - list of unique FiniteElements for Functions
        format     - the format used to build the Form (a dictionary)

    A multi-linear form is first expressed as an element of the
    algebra (a Sum) and is then post-processed to generate a sum
    of ElementTensors, where each ElementTensor is expressed as
    a product of a ReferenceTensor and a GeometryTensor."""

    def __init__(self, sum, name):
        "Create Form."

        # Initialize Form
        self.sum        = Sum(sum)
        self.name       = name
        self.AKi        = None
        self.AKb        = None
        self.rank       = None
        self.dims       = None
        self.indices    = None
        self.nfunctions = 0
        self.nconstants = 0
        self.test       = None
        self.trial      = None
        self.elements   = None
        self.format     = None

        # Reassign indices
        debug("Before index reassignment: " + str(sum), 2)
        reassign_indices(self.sum)

        return

    def reference_tensor(self, term = None):
        "Return interior reference tensor for given term."
        if term == None:
            if len(self.AKi.terms) > 1:
                raise RuntimeError, "Form has more than one term and term not specified."
            else:
                return self.AKi.terms[0].A0.A0
        else:
            return self.AKi.terms[term].A0.A0

    def primary_indices(self, term = None):
        "Return primary indices for interior reference tensor."
        if term == None:
            if len(self.AKi.terms) > 1:
                raise RuntimeError, "Form has more than one term and term not specified."
            else:
                return self.AKi.terms[0].A0.i.indices
        else:
            return self.AKi.terms[term].A0.i.indices

    def secondary_indices(self, term = None):
        "Return primary indices for interior reference tensor."
        if term == None:
            if len(self.AKi.terms) > 1:
                raise RuntimeError, "Form has more than one term and term not specified."
            else:
                return self.AKi.terms[0].A0.a.indices
        else:
            return self.AKi.terms[term].A0.a.indices

    def __repr__(self):
        "Print nicely formatted representation of Form."
        return str(self.sum)
