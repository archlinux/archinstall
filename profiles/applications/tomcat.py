import archinstall

# This is using Tomcat 10 as that is the latest release at the time of implementation.
# This should probably be updated to use newer releases as they come out.

# Define the package list in order for lib to source
# which packages will be installed by this profile
__packages__ = ["tomcat10"]

installation.add_additional_packages(__packages__)

installation.enable_service('tomcat10')
