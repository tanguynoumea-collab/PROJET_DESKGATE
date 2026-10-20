# SPDX-License-Identifier: MIT
"""Capacités BIM de Deskgate (MIT). N'importe jamais bcf-client ni deskgate_bcf (règle 10)."""

import os

# OpenBLAS réserve des tampons par thread dès l'import de numpy : sous plafond mémoire du Job,
# l'import échoue sans ces valeurs (Pitfall 1). Posées avant tout import de numpy/ifcopenshell.
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "NUMEXPR_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_name, "1")

__version__ = "0.1.0.dev0"
