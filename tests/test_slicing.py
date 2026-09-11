import json
import sys
import tempfile
import unittest
from pathlib import Path
from cadkit import slicing as slice_report


class SliceReportMetadataTests(unittest.TestCase):

    def test_prusa_or_orca_footer(self):
        stats = slice_report.parse_gcode(
            "\n; filament used [mm] = 1182.01, 17.99\n; filament used [g] = 3.53, 0.07\n; filament cost = 0.08, 0.01; total filament used [g] = 3.60\n; total filament cost = 0.09\n; total layers count = 137\n; estimated printing time (normal mode) = 1h 3m 15s\n"
        )
        self.assertAlmostEqual(stats.filament_g, 3.6)
        self.assertAlmostEqual(stats.filament_m, 1.2)
        self.assertAlmostEqual(stats.reported_cost, 0.09)
        self.assertEqual(stats.model_time_s, 3795)
        self.assertEqual(stats.layers, 137)

    def test_bambu_header(self):
        stats = slice_report.parse_gcode(
            "\n; HEADER_BLOCK_START\n; BambuStudio 02.02.02.56\n; model printing time: 7m 41s; total estimated time: 15m 33s\n; total layer number: 30\n; total filament length [mm] : 316.27\n; total filament volume [cm^3] : 760.72\n; total filament weight [g] : 0.95\n; filament_density: 1.25\n; filament_diameter: 1.75\n; HEADER_BLOCK_END\n"
        )
        self.assertAlmostEqual(stats.filament_g, 0.95)
        self.assertAlmostEqual(stats.filament_m, 0.31627)
        self.assertEqual(stats.model_time_s, 461)
        self.assertEqual(stats.total_time_s, 933)
        self.assertEqual(stats.layers, 30)

    def test_profile_inheritance_and_includes_are_flattened(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "machine"
            root.mkdir()
            (root / "base.json").write_text(
                json.dumps(
                    {
                        "type": "machine",
                        "name": "base",
                        "speed": "100",
                        "shared": "base",
                    }
                )
            )
            (root / "gcode.json").write_text(
                json.dumps(
                    {"type": "machine", "name": "gcode", "machine_start_gcode": "G28"}
                )
            )
            leaf = root / "printer.json"
            leaf.write_text(
                json.dumps(
                    {
                        "type": "machine",
                        "name": "printer",
                        "inherits": "base",
                        "include": ["gcode"],
                        "shared": "leaf",
                    }
                )
            )
            flattened = slice_report.flatten_bambu_profile(leaf)
            self.assertEqual(flattened["speed"], "100")
            self.assertEqual(flattened["machine_start_gcode"], "G28")
            self.assertEqual(flattened["shared"], "leaf")
            self.assertNotIn("inherits", flattened)
            self.assertNotIn("include", flattened)


if __name__ == "__main__":
    unittest.main()
