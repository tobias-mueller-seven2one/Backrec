"""Kept so the manual route `pythonw main.pyw` still opens the window.

Three lines and no logic of its own. The way the README used to advertise must
not break unannounced, but it has no business carrying anything the package
does not already do (design D1).
"""

import sys

from backrec.app import main

sys.exit(main())
