.. _archinstall.Profile:

archinstall.Profile
===================

This class enables access to pre-programmed profiles.
This is not to be confused with :ref:`archinstall.Application` which is for pre-programmed application profiles.

Profiles in general is a set or group of installation steps.
Where as applications are a specific set of instructions for a very specific application.

An example would be the *(currently fictional)* profile called `database`.
The profile `database` might contain the application profile `postgresql`.
And that's the difference between :ref:`archinstall.Profile` and :ref:`archinstall.Application`.

.. autofunction:: archinstall.Profile
