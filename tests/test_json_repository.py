import json
import os
import tempfile
import pytest
from opctl.adapters.json_repository import JsonPolicyRepository


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
