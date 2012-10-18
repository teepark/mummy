import os

os.chdir('python')

link_name = "pip-egg-info"
source = os.path.join('..', link_name)
if not os.path.exists(link_name) and os.path.exists(source):
    os.symlink(source, link_name)

if os.path.exists("paver-minilib.zip"):
    import sys
    sys.path.insert(0, "paver-minilib.zip")

import paver.tasks
paver.tasks.main()
