import os
import shutil
import unittest

from src.net_mgmt.db import get_database, set_db_path


class TestDB(unittest.TestCase):
    def setUp(self):
        # Create two different network directories
        self.dir1 = "networks_db_test_1"
        self.dir2 = "networks_db_test_2"
        os.makedirs(self.dir1, exist_ok=True)
        os.makedirs(self.dir2, exist_ok=True)

        with open(os.path.join(self.dir1, "net1.yaml"), "w") as f:
            f.write("cidr: 10.1.0.0/24\nname: net1")

        with open(os.path.join(self.dir2, "net2.yaml"), "w") as f:
            f.write("cidr: 10.2.0.0/24\nname: net2")

    def tearDown(self):
        shutil.rmtree(self.dir1)
        shutil.rmtree(self.dir2)
        # Reset global state
        set_db_path("networks")

    def test_switch_database(self):
        # Load first DB
        set_db_path(self.dir1)
        nets1 = get_database(force_reload=True)  # Ensure clean start
        self.assertEqual(len(nets1), 1)
        self.assertEqual(nets1[0].cidr.network_address.exploded, "10.1.0.0")

        # Switch to second DB
        set_db_path(self.dir2)
        # Should automatically reload because set_db_path invalidates cache
        nets2 = get_database()
        self.assertEqual(len(nets2), 1)
        self.assertEqual(nets2[0].cidr.network_address.exploded, "10.2.0.0")

    def test_cache_invalidation(self):
        set_db_path(self.dir1)
        get_database(force_reload=True)

        # Check cache is populated (implementation detail, but good for verification)
        from src.net_mgmt import db

        self.assertIsNotNone(db._DB_CACHE)

        # Change path, cache should be cleared
        set_db_path(self.dir2)
        self.assertIsNone(db._DB_CACHE)


if __name__ == "__main__":
    unittest.main()
