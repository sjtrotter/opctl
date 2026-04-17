import pytest
from opctl.domain.interfaces import IProvider
from opctl.infrastructure._resolve import resolve_provider


class _AvailableProvider(IProvider):
    @classmethod
    def provider_name(cls): return "available"
    @classmethod
    def is_available(cls): return True


class _UnavailableProvider(IProvider):
    @classmethod
    def provider_name(cls): return "unavailable"
    @classmethod
    def is_available(cls): return False


class _SecondAvailableProvider(IProvider):
    @classmethod
    def provider_name(cls): return "second"
    @classmethod
    def is_available(cls): return True


class TestResolveProvider:

    def test_auto_selects_first_available(self):
        result = resolve_provider("auto", [_UnavailableProvider, _AvailableProvider])
        assert isinstance(result, _AvailableProvider)

    def test_auto_skips_unavailable(self):
        result = resolve_provider("auto", [_UnavailableProvider, _SecondAvailableProvider])
        assert isinstance(result, _SecondAvailableProvider)

    def test_auto_picks_first_when_multiple_available(self):
        result = resolve_provider("auto", [_AvailableProvider, _SecondAvailableProvider])
        assert isinstance(result, _AvailableProvider)

    def test_auto_raises_when_none_available(self):
        with pytest.raises(RuntimeError, match="No available provider"):
            resolve_provider("auto", [_UnavailableProvider])

    def test_named_returns_correct_provider(self):
        result = resolve_provider("second", [_AvailableProvider, _SecondAvailableProvider])
        assert isinstance(result, _SecondAvailableProvider)

    def test_named_raises_for_unknown_name(self):
        with pytest.raises(ValueError, match="Provider 'ghost' not found"):
            resolve_provider("ghost", [_AvailableProvider])

    def test_named_raises_even_if_provider_unavailable(self):
        with pytest.raises(ValueError, match="Provider 'unavailable' not found"):
            resolve_provider("unavailable", [_AvailableProvider])

    def test_named_ignores_availability_check(self):
        # Named selection should instantiate even if is_available returns False —
        # but the current impl only searches by name in the candidates list,
        # so unavailable is not in the list when filtered. This verifies that
        # passing it directly does NOT call is_available().
        class _ForcedProvider(IProvider):
            @classmethod
            def provider_name(cls): return "forced"
            @classmethod
            def is_available(cls): return False

        result = resolve_provider("forced", [_ForcedProvider])
        assert isinstance(result, _ForcedProvider)
