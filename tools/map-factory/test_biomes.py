"""Environment choice and theme-fit tree palettes; no game and no network.

The environment is the map's built-in theme: the game loads
`<environment>Prefabs` and the tree prefabs that come with those scenes, so a
palette outside the environment's set is a missing tree, not a mood.
"""

import unittest

import numpy as np

import resources as R


def ground(level, size=400):
    return np.full((size, size), float(level))


def flat_water(size=400):
    return np.zeros((size, size), np.uint16)


class EnvironmentChoiceTests(unittest.TestCase):
    def test_tropical_lowland(self):
        sq = {"lat": -22.94, "lon": -43.205}
        environment, receipt = R.choose_environment(sq, ground(95), flat_water())
        self.assertEqual(environment, "Tropical", receipt)
        self.assertEqual(receipt["rule"], "tropical lowland")

    def test_temperate_lowland_stays_sunny(self):
        sq = {"lat": 35.58, "lon": -82.555}
        terrain = np.linspace(80, 480, 400)[None, :] * np.ones((400, 1))
        environment, receipt = R.choose_environment(sq, terrain, flat_water())
        self.assertEqual(environment, "Sunny", receipt)

    def test_alpine_in_europe_gets_the_european_palette(self):
        sq = {"lat": 47.27, "lon": 11.4}
        terrain = np.linspace(60, 1000, 400)[None, :] * np.ones((400, 1))
        environment, receipt = R.choose_environment(sq, terrain, flat_water())
        self.assertEqual(environment, "Europe", receipt)
        self.assertGreaterEqual(receipt["high_ground_share"], R.ALPINE_HIGH_SHARE)

    def test_alpine_outside_europe_keeps_north_american_architecture(self):
        sq = {"lat": 39.74, "lon": -104.99}
        terrain = np.linspace(60, 1000, 400)[None, :] * np.ones((400, 1))
        environment, _ = R.choose_environment(sq, terrain, flat_water())
        self.assertEqual(environment, "North")

    def test_high_latitude_is_north_whatever_the_relief(self):
        sq = {"lat": 61.2, "lon": 25.0}
        environment, receipt = R.choose_environment(sq, ground(120), flat_water())
        self.assertEqual(environment, "North", receipt)
        self.assertEqual(receipt["rule"], "high latitude")

    def test_tropical_highland_is_not_the_palm_theme(self):
        sq = {"lat": -13.5, "lon": -71.97}
        terrain = np.linspace(1200, 1800, 400)[None, :] * np.ones((400, 1))
        environment, _ = R.choose_environment(sq, terrain, flat_water())
        self.assertEqual(environment, "North")

    def test_water_is_ignored_and_explicit_choice_wins(self):
        sq = {"lat": -22.94, "lon": -43.205}
        depth = flat_water().copy()
        depth[:] = 400  # shallow sea everywhere
        knobs = R.Knobs(environment="Europe")
        environment, receipt = R.choose_environment(sq, ground(200), depth, knobs)
        self.assertEqual(environment, "Europe")
        self.assertEqual(receipt["rule"], "explicit")
        with self.assertRaises(ValueError):
            R.choose_environment(sq, ground(200), flat_water(), R.Knobs(environment="Mars"))


class PaletteTests(unittest.TestCase):
    def test_every_palette_stays_inside_its_environment(self):
        for environment, pools in R.THEMES.items():
            used = {name for pool in pools.values() for name, _ in pool}
            self.assertLessEqual(used, set(R.VANILLA_TREES[environment]), environment)

    def test_roles_match_the_biome(self):
        self.assertIn("palm", R.THEMES["Tropical"])
        self.assertNotIn("palm", R.THEMES["Sunny"])
        self.assertNotIn("conifer", R.THEMES["Sunny"])
        for environment in ["North", "Europe"]:
            self.assertIn("conifer", R.THEMES[environment], environment)
        for environment in ["Sunny", "Tropical"]:
            self.assertNotIn("conifer", R.THEMES[environment], environment)

    def test_tropical_palms_favour_low_ground(self):
        """species() takes the coasts for palms and leaves the hills broadleaf."""
        size = 1081
        terrain = np.repeat(np.linspace(0, 1000, size)[:, None], size, axis=1)
        wet = np.zeros((size, size), bool)
        slope = np.zeros((size, size))
        rng = np.random.default_rng(0)
        x_steps = np.zeros(400, np.int16)
        px = np.full(400, int(round(-3000 / R.TREE_UNIT)), np.int16)

        def palms(z_metres):
            kinds = R.species(
                px,
                np.full(400, int(round(z_metres / R.TREE_UNIT)), np.int16),
                np.zeros(400, np.uint8),
                terrain,
                wet,
                slope,
                rng,
                "Tropical",
                np.random.default_rng(7),
            )
            names = np.array([R.TREE_NAMES[i] for i in kinds])
            return float(np.char.startswith(names.astype(str), "palm").mean())

        # z=-7000 near the south edge is low ground here; z=+7000 is high.
        self.assertGreater(palms(-7000), 0.5)
        self.assertLessEqual(palms(7000), 0.5)

    def test_tree_budget_is_explicit(self):
        budget = R.tree_budget({"trees": (np.zeros(180_000), np.zeros(180_000), np.zeros(180_000, np.uint16))})
        self.assertEqual(
            budget,
            {
                "planted": 180_000,
                "editor_cap": 250_000,
                "planting_headroom": 70_000,
                "manager_slots": R.TREE_SLOTS,
                "free_slots": R.TREE_SLOTS - 180_000,
            },
        )


if __name__ == "__main__":
    unittest.main()
