import json
import os
import sys
import tempfile
from unittest.mock import patch
import pytest
from opctl.adapters.json_repository import JsonPolicyRepository, SessionLockError


class TestJsonPolicyRepository:

    def _tmp_path(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)
        return path

    def test_save_writes_valid_json(self):
        path = self._tmp_path()
        try:
            repo = JsonPolicyRepository(path)
            repo.save_state({"key": "value"})
            with open(path) as f:
                data = json.load(f)
            assert data == {"key": "value"}
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_load_reads_json(self):
        path = self._tmp_path()
        try:
            with open(path, "w") as f:
                json.dump({"hostname": "testbox"}, f)
            repo = JsonPolicyRepository(path)
            data = repo.load_state()
            assert data == {"hostname": "testbox"}
        finally:
            os.unlink(path)

    def test_load_returns_empty_dict_when_file_missing(self):
        repo = JsonPolicyRepository("/tmp/does_not_exist_opctl_test.json")
        assert repo.load_state() == {}

    def test_round_trip(self):
        path = self._tmp_path()
        try:
            repo = JsonPolicyRepository(path)
            original = {"system": {"hostname": "ops-box"}, "backend": {"firewall_provider": "ufw"}}
            repo.save_state(original)
            loaded = repo.load_state()
            assert loaded == original
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_load_returns_empty_dict_on_corrupt_json(self):
        path = self._tmp_path()
        try:
            with open(path, "w") as f:
                f.write("{ not valid json }")
            repo = JsonPolicyRepository(path)
            assert repo.load_state() == {}
        finally:
            os.unlink(path)

    def test_load_returns_empty_dict_on_non_dict_json(self):
        """Valid JSON that isn't an object (a list, a scalar) must normalize to {}.

        Downstream OpProfile.from_dict assumes a mapping; a top-level list would
        otherwise crash callers with an AttributeError on .get().
        """
        path = self._tmp_path()
        try:
            with open(path, "w") as f:
                f.write("[1, 2, 3]")
            repo = JsonPolicyRepository(path)
            assert repo.load_state() == {}
        finally:
            os.unlink(path)

    def test_atomic_write_leaves_no_temp_file(self):
        path = self._tmp_path()
        try:
            JsonPolicyRepository(path).save_state({"a": 1})
            directory = os.path.dirname(path) or "."
            assert [n for n in os.listdir(directory) if n.startswith(".session-")] == []
        finally:
            for n in (path, path + ".lock"):
                if os.path.exists(n):
                    os.unlink(n)

    def test_lock_released_between_saves(self):
        path = self._tmp_path()
        try:
            repo = JsonPolicyRepository(path)
            repo.save_state({"a": 1})
            repo.save_state({"a": 2})   # must not deadlock or fail on the second write
            assert repo.load_state() == {"a": 2}
        finally:
            for n in (path, path + ".lock"):
                if os.path.exists(n):
                    os.unlink(n)

    def test_failed_write_keeps_original_and_cleans_temp(self):
        # The durability guarantee: a crash mid-write leaves the prior file intact
        # and removes the temp file.
        path = self._tmp_path()
        try:
            repo = JsonPolicyRepository(path)
            repo.save_state({"a": 1})
            with patch("opctl.adapters.json_repository.os.replace", side_effect=OSError("boom")):
                with pytest.raises(OSError):
                    repo.save_state({"a": 2})
            assert repo.load_state() == {"a": 1}          # original untouched
            directory = os.path.dirname(path) or "."
            assert [n for n in os.listdir(directory) if n.startswith(".session-")] == []
        finally:
            for n in (path, path + ".lock"):
                if os.path.exists(n):
                    os.unlink(n)

    def test_lock_released_after_failed_write(self):
        path = self._tmp_path()
        try:
            repo = JsonPolicyRepository(path)
            with patch("opctl.adapters.json_repository.os.replace", side_effect=OSError("boom")):
                with pytest.raises(OSError):
                    repo.save_state({"a": 1})
            repo.save_state({"a": 2})                       # lock was released despite the failure
            assert repo.load_state() == {"a": 2}
        finally:
            for n in (path, path + ".lock"):
                if os.path.exists(n):
                    os.unlink(n)

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX fcntl flock test")
    def test_save_state_fails_fast_when_locked(self):
        import fcntl
        path = self._tmp_path()
        lock_path = path + ".lock"
        holder = open(lock_path, "a+")
        try:
            fcntl.flock(holder.fileno(), fcntl.LOCK_EX)
            with pytest.raises(SessionLockError):
                JsonPolicyRepository(path).save_state({"a": 1})
        finally:
            fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
            holder.close()
            for n in (path, lock_path):
                if os.path.exists(n):
                    os.unlink(n)
