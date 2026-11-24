import unittest

from vigil.system_info import zone_mounts


class SystemInfoTest(unittest.TestCase):
    def test_mount_points_include_children_and_ignore_prefix_collision(self):
        result = zone_mounts([
            "10 1 8:1 / /investigation/disk\\040A ro,nosuid - ext4 /dev/sda1 rw",
            "11 1 8:2 / /stockage rw - xfs /dev/sdb1 rw",
            "12 1 8:3 / /stockage-backup rw - ext4 /dev/sdc1 rw",
        ])
        self.assertEqual(result["/investigation"], [
            ("/investigation/disk A", "/dev/sda1", "ext4", "ro"),
        ])
        self.assertEqual(result["/stockage"], [
            ("/stockage", "/dev/sdb1", "xfs", "rw"),
        ])
