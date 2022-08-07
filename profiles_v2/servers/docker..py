from profiles_v2.profiles import Profile, ProfileType


class DockerProfile(Profile):
	def __init__(self):
		super().__init__('Docker', ProfileType.Server)

	def packages(self) -> List[str]:
		return ['docker']

	def services_to_enable(self):
		return ['docker']
