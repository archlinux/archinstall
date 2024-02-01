import glob
import pathlib

print("The following are viable --script options:")

for script in [pathlib.Path(x) for x in glob.glob(f"{pathlib.Path(__file__).parent}/*.py")]:
	if script.stem in ['__init__', 'list']:
		continue

	print(f"    {script.stem}")