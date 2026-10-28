from pathlib import Path

import pytest

from archinstall.lib.models.device import (
	FilesystemType,
	ModificationStatus,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	Unit,
)


def _make(
	sector_size: SectorSize,
	status: ModificationStatus,
	length: Size,
	dev_path: Path | None = None,
) -> PartitionModification:
	return PartitionModification(
		status=status,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, sector_size),
		length=length,
		fs_type=FilesystemType.EXT4,
		mountpoint=Path('/'),
		dev_path=dev_path,
	)


@pytest.mark.parametrize(
	'length',
	[
		Size(0, Unit.B, SectorSize.default()),
		Size(0, Unit.sectors, SectorSize.default()),
	],
)
def test_a_created_partition_needs_a_length(length: Size) -> None:
	"""A zero-length partition cannot be written to a disk."""
	with pytest.raises(ValueError, match='needs a length'):
		_make(SectorSize.default(), ModificationStatus.CREATE, length)


def test_a_created_partition_with_a_length_is_accepted() -> None:
	sector_size = SectorSize.default()

	part = _make(sector_size, ModificationStatus.CREATE, Size(1, Unit.MiB, sector_size))

	assert part.end > part.start


def test_existing_partitions_report_their_length() -> None:
	"""EXIST and MODIFY describe what is on the disk, so their length is not up for
	validation - a partition found on the disk is accepted as it is."""
	sector_size = SectorSize.default()

	for status in (ModificationStatus.EXIST, ModificationStatus.MODIFY):
		part = _make(sector_size, status, Size(0, Unit.B, sector_size), Path('/dev/sda1'))
		assert part.length == Size(0, Unit.B, sector_size)
