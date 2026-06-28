.. _archinstall.Plugins:

Python Plugins
==============

``archinstall`` supports plugins via two methods.

First method is directly via the ``--plugin`` parameter when running as a CLI tool. This will load a specific plugin locally or remotely via a path.

The second method is via Python's built in `plugin discovery`_ using `entry points`_ categorized as ``archinstall.plugin``.

``--plugin`` parameter
----------------------

The parameter has the benefit of being stored in the ``--conf`` state, meaning when re-running an installation — the plugin will automatically be loaded.
It's limitation is that it requires an initial path to be known and written and be cumbersome.

Plugin Discovery
----------------

This method allows for multiple plugins to be loaded with the drawback that they have to be installed beforehand on the system running ``archinstall``.
This mainly targets those who build their own ISO's and package specific setups for their needs.


What's supported?
-----------------

Currently the documentation for this is scarse. Until that is resolved, the best way to find supported features is to search the source code for `plugin.on_ <https://github.com/search?q=repo%3Aarchlinux%2Farchinstall+%22plugin.on_%22&type=code>`_ as this will give a clear indication of which calls are made to plugins.

How does it work?
-----------------

``archinstall`` plugins use a discovery-driven approach where plugins are queried for certain functions.
As an example, if a plugin has the following function:

.. code-block:: python

   def on_pacstrap(*packages):
       ...

The function :code:`archinstall.Pacman().strap(["some packages"])` is hardcoded to iterate plugins and look for :code:`on_pacstrap` in the plugin.
If the function exists, :code:`.strap()` will call the plugin's function and replace the initial package list with the result from the plugin.

The best way to document these calls is currently undecided, as it's hard to document this behavior dynamically.

Writing your own?
-----------------

The simplest way currently is to look at a reference implementation or the community. Two of these are:

* `torxed/archinstall-aur <https://github.com/torxed/archinstall-aur>`_
* `phisch/archinstall-aur <https://github.com/phisch/archinstall-aur>`_

And search for `plugin.on_ <https://github.com/search?q=repo%3Aarchlinux%2Farchinstall+%22plugin.on_%22&type=code>`_ in the code base to find what ``archinstall`` will look for. PR's are welcome to widen the support for this.

.. _plugin discovery: https://packaging.python.org/en/latest/specifications/entry-points/
.. _entry points: https://docs.python.org/3/library/importlib.metadata.html#entry-points
