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


class TestEntityCache(unittest.TestCase):
    def setUp(self):
        self.db_dir = "networks_cache_test"
        os.makedirs(self.db_dir, exist_ok=True)
        os.makedirs(os.path.join(self.db_dir, "epgs"), exist_ok=True)
        set_db_path(self.db_dir)

    def tearDown(self):
        shutil.rmtree(self.db_dir)
        set_db_path("networks")

    def test_entity_cache_hits_and_mtime_invalidation(self):
        from src.net_mgmt import db

        epg_file = os.path.join(self.db_dir, "epgs", "EPG_App.yaml")
        with open(epg_file, "w") as f:
            f.write("vlan: 30\n")

        # 1. First load (should read disk)
        data1 = db.get_cached_entities("epgs")
        self.assertEqual(data1.get("EPG_App"), {"vlan": 30})

        # 2. Second load (should hit in-memory cache, returning identical object reference)
        data2 = db.get_cached_entities("epgs")
        self.assertIs(data1, data2)

        # 3. Modify file content and shift mtime forward to force reload
        curr_mtime = os.path.getmtime(epg_file)
        new_mtime = curr_mtime + 5.0

        with open(epg_file, "w") as f:
            f.write("vlan: 40\n")
        os.utime(epg_file, (new_mtime, new_mtime))

        # 4. Third load (should detect mtime shift, invalidate, and reload from disk)
        data3 = db.get_cached_entities("epgs")
        self.assertEqual(data3.get("EPG_App"), {"vlan": 40})
        self.assertIsNot(data1, data3)

    def test_entity_cache_cleared_on_set_db_path(self):
        from src.net_mgmt import db

        epg_file = os.path.join(self.db_dir, "epgs", "EPG_App.yaml")
        with open(epg_file, "w") as f:
            f.write("vlan: 30\n")

        db.get_cached_entities("epgs")
        self.assertIn((self.db_dir, "epgs"), db._ENTITY_CACHE)

        # Changing DB path should completely clear entity cache
        set_db_path("networks")
        self.assertEqual(len(db._ENTITY_CACHE), 0)

    def test_entity_cache_cleared_on_save_and_write(self):
        from src.net_mgmt import db

        epg_file = os.path.join(self.db_dir, "epgs", "EPG_App.yaml")
        with open(epg_file, "w") as f:
            f.write("vlan: 30\n")

        db.get_cached_entities("epgs")
        self.assertIn((self.db_dir, "epgs"), db._ENTITY_CACHE)

        # Triggering clear_db_cache (which is called on save() or programmatic writes)
        db.clear_db_cache()
        self.assertEqual(len(db._ENTITY_CACHE), 0)
        self.assertIsNone(db._DB_CACHE)


if __name__ == "__main__":
    unittest.main()
