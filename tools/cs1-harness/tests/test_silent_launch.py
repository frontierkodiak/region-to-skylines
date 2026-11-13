"""Exercise real launch shells, including a runtime that discards audio env."""

import json
import os
import pathlib
import socket
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from cs1_harness import audio
from cs1_harness.config import Config
from cs1_harness.setup import LAUNCH_SH
from cs1_harness.steam import backend
from cs1_harness.session import Session
from cs1_harness.client import HarnessError


class SilentLaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="silent launch ")
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.cfg = Config.for_host()
        self.cfg.harness_home = self.root
        audio.prepare(self.cfg)
        self.pulse = socket.socket(socket.AF_UNIX)
        self.pulse.bind(str(self.root / "run-audio/pulse"))
        self.addCleanup(self.pulse.close)

    def test_alsa_config_has_only_null_endpoints(self):
        self.assertEqual((self.root / "run-audio/alsa.conf").read_text(), audio.ALSA_CONFIG)
        self.assertEqual(audio.ALSA_CONFIG, "pcm.default { type null }\npcm.null { type null }\n")
        self.assertTrue(stat.S_ISSOCK((self.root / "run-audio/pulse").stat().st_mode))
        with self.assertRaises(RuntimeError):
            audio.prepare(self.cfg)

    def test_flatpak_shell_applies_environment_after_metadata_filter(self):
        steam = backend(self.cfg)
        argv = steam.shell_argv("exec python3 -c 'import os,json; print(json.dumps(dict(os.environ)))'")
        # Execute the exact post-Flatpak command with none of the audio env inherited.
        cmd = ["sh", *argv[argv.index("-c") :]]
        env = {k: v for k, v in os.environ.items() if k not in audio.environment(self.cfg)}
        result = subprocess.run(cmd, env=env, text=True, capture_output=True, check=True)
        actual = json.loads(result.stdout)
        for key, value in audio.environment(self.cfg).items():
            self.assertEqual(actual[key], value)
        steam_cmd = steam.steam_argv(["-silent", "-applaunch", "255710"])
        self.assertIn("--command=sh", steam_cmd)
        self.assertIn('exec /app/bin/steam "$@"', steam_cmd[steam_cmd.index("-c") + 1])
        self.assertEqual(steam_cmd[-3:], ["-silent", "-applaunch", "255710"])

    def test_private_bus_activation_carries_audio_route_to_nested_portal(self):
        session = Session(self.cfg, self.root / "stage")
        with (
            patch.dict(os.environ, XDG_RUNTIME_DIR=str(self.root)),
            patch.object(session, "unit") as start,
            patch.object(pathlib.Path, "exists", return_value=True),
        ):
            session.start_display()
        bus_call = next(call for call in start.call_args_list if call.args[0] == self.cfg.dbus_unit)
        for key, value in audio.environment(self.cfg).items():
            self.assertEqual(bus_call.kwargs["env"][key], value)

    def test_nested_game_shell_reapplies_environment_and_preserves_arguments(self):
        wrapper = self.root / "launch.sh"
        wrapper.write_text(LAUNCH_SH)
        game_dir = self.root / "Cities_Skylines"
        game_dir.mkdir()
        game = game_dir / "Cities.x64"
        game.write_text(
            '#!/usr/bin/python3\nimport os,json,sys\nprint(json.dumps({"env":dict(os.environ),"args":sys.argv[1:]}))\n'
        )
        game.chmod(0o755)
        runtime = self.root / "runtime"
        # Model pressure-vessel replacing audio env between Steam and the game shell.
        runtime.write_text(
            "#!/usr/bin/python3\nimport os,sys\nenv=dict(os.environ)\n"
            + "".join(f"env.pop({key!r},None)\n" for key in audio.environment(self.cfg))
            + "os.execvpe(sys.argv[1],sys.argv[1:],env)\n"
        )
        runtime.chmod(0o755)
        output = self.root / "stdout"
        (self.root / "session.env").write_text(
            f"CS1_HARNESS_DISPLAY=:57\nCS1_HARNESS_VGL='{self.root}'\n"
            f"CS1_HARNESS_EGL=egl0\nCS1_HARNESS_PORT=8779\nCS1_HARNESS_STDOUT='{output}'\n"
        )
        subprocess.run(
            ["sh", str(wrapper), str(runtime), str(game_dir / "dowser"), "argument with spaces"],
            env=dict(os.environ, DISPLAY=":57"),
            check=True,
            capture_output=True,
        )
        actual = json.loads(output.read_text().splitlines()[-1])
        self.assertEqual(actual["args"], ["argument with spaces"])
        for key, value in audio.environment(self.cfg).items():
            self.assertEqual(actual["env"][key], value)
        # Outside the harness display, the wrapper does not change the game command.
        result = subprocess.run(
            ["sh", str(wrapper), "/bin/echo", "unchanged"],
            env=dict(os.environ, DISPLAY=":99"),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(result.stdout, "unchanged\n")
        refused = subprocess.run(
            ["sh", str(wrapper), "/bin/echo", "must not execute"],
            env=dict(os.environ, DISPLAY=":57"),
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertNotIn("must not execute", refused.stdout)

    def test_game_environment_and_device_receipts_are_required(self):
        session = Session(self.cfg, self.root / "stage")
        good = {
            "pid": 123,
            "name": "Cities.x64",
            "audio_environment": audio.environment(self.cfg),
            "physical_audio_fds": [],
            "pulse_endpoint": {"kind": "socket", "run_owned": True},
            "flatpak_pulse_endpoint": {"kind": "absent", "run_owned": False},
        }
        with patch("cs1_harness.audio.processes", return_value=[good]):
            session.check_audio()
        for rows in ([], [dict(good, audio_environment={})], [dict(good, physical_audio_fds=["/dev/snd/pcmC0D0p"])]):
            with patch("cs1_harness.audio.processes", return_value=rows):
                with self.assertRaises(HarnessError):
                    session.check_audio()

    def test_late_webhelper_host_socket_is_rejected_but_private_socket_alias_is_allowed(self):
        namespace = self.root / "nested-root"
        alias = namespace / "run/flatpak/pulse/native"
        alias.parent.mkdir(parents=True)
        # Reproduce the exact PM finding, with a real reachable Unix socket.
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(alias))
            server.listen()
            bad = audio.pulse_endpoint(namespace, "unix:/run/flatpak/pulse/native", self.cfg)
            self.assertEqual(bad["kind"], "socket")
            self.assertFalse(bad["run_owned"])
        alias.unlink()
        os.link(self.root / "run-audio/pulse", alias)
        good = audio.pulse_endpoint(namespace, "unix:/run/flatpak/pulse/native", self.cfg)
        self.assertEqual(good["kind"], "socket")
        self.assertTrue(good["run_owned"])
        row = {
            "pid": 456,
            "name": "steamwebhelper",
            "physical_audio_fds": [],
            "audio_environment": dict(
                audio.environment(self.cfg),
                PULSE_SERVER="unix:/run/flatpak/pulse/native",
                PULSE_CLIENTCONFIG="/run/flatpak/pulse/config",
            ),
            "pulse_endpoint": bad,
            "flatpak_pulse_endpoint": bad,
        }
        self.assertTrue(audio.violations(self.cfg, [row], require_game=False))
        row.update(pulse_endpoint=good, flatpak_pulse_endpoint=good)
        self.assertEqual(audio.violations(self.cfg, [row], require_game=False), [])
        # A different regular file is not proof of our run-local endpoint.
        alias.unlink()
        alias.touch()
        other = audio.pulse_endpoint(namespace, "unix:/run/flatpak/pulse/native", self.cfg)
        row.update(pulse_endpoint=other)
        self.assertTrue(audio.violations(self.cfg, [row], require_game=False))

    def test_stale_wrapper_fails_before_starting_steam(self):
        session = Session(self.cfg, self.root / "stage")
        with patch.object(session, "unit") as start:
            with self.assertRaisesRegex(HarnessError, "wrapper is out of date"):
                session.launch([])
            start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
