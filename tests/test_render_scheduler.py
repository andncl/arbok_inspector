"""Tests for the coalescing RenderScheduler."""
import asyncio

from arbok_inspector.helpers.render_scheduler import RenderScheduler


class SlowRender:
    """Render callback that records calls and takes `duration` seconds."""

    def __init__(self, duration: float = 0.05, fail_on: set[int] | None = None):
        self.duration = duration
        self.calls: list[bool] = []
        self.running = 0
        self.max_running = 0
        self.fail_on = fail_on or set()

    async def __call__(self, reload: bool) -> None:
        self.calls.append(reload)
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        try:
            await asyncio.sleep(self.duration)
            if len(self.calls) in self.fail_on:
                raise RuntimeError("render failed")
        finally:
            self.running -= 1


def run(coro):
    return asyncio.run(coro)


class TestRenderScheduler:

    def test_single_request_renders_once(self):
        async def scenario():
            render = SlowRender()
            scheduler = RenderScheduler(render)
            scheduler.request()
            await scheduler.wait_idle()
            return render
        assert run(scenario()).calls == [False]

    def test_burst_is_coalesced_into_one_follow_up(self):
        """50 slider events during a render → current render + 1 follow-up."""
        async def scenario():
            render = SlowRender(duration=0.05)
            scheduler = RenderScheduler(render)
            for _ in range(50):
                scheduler.request()
                await asyncio.sleep(0.001)
            await scheduler.wait_idle()
            return render
        render = run(scenario())
        assert 2 <= len(render.calls) <= 3

    def test_never_renders_concurrently(self):
        async def scenario():
            render = SlowRender(duration=0.01)
            scheduler = RenderScheduler(render)
            for _ in range(20):
                scheduler.request()
                await asyncio.sleep(0.004)
            await scheduler.wait_idle()
            return render
        assert run(scenario()).max_running == 1

    def test_reload_is_not_lost_when_merged(self):
        """A reload request merged with plain requests still reloads."""
        async def scenario():
            render = SlowRender(duration=0.03)
            scheduler = RenderScheduler(render)
            scheduler.request()
            await asyncio.sleep(0.005)
            scheduler.request()
            scheduler.request(reload=True)
            scheduler.request()
            await scheduler.wait_idle()
            return render
        assert run(scenario()).calls == [False, True]

    def test_last_render_sees_latest_state(self):
        """The final render happens after the last request (no stale end state)."""
        async def scenario():
            state = {"value": 0}
            seen = []

            async def render(reload):
                seen.append(state["value"])
                await asyncio.sleep(0.02)
            scheduler = RenderScheduler(render)
            for value in range(1, 11):
                state["value"] = value
                scheduler.request()
                await asyncio.sleep(0.003)
            await scheduler.wait_idle()
            return seen
        assert run(scenario())[-1] == 10

    def test_failing_render_does_not_break_scheduler(self):
        async def scenario():
            render = SlowRender(duration=0.01, fail_on={1})
            scheduler = RenderScheduler(render)
            scheduler.request()
            await scheduler.wait_idle()
            scheduler.request()
            await scheduler.wait_idle()
            return render
        assert len(run(scenario()).calls) == 2

    def test_busy_flag(self):
        async def scenario():
            scheduler = RenderScheduler(SlowRender(duration=0.02))
            assert not scheduler.busy
            scheduler.request()
            assert scheduler.busy
            await scheduler.wait_idle()
            assert not scheduler.busy
        run(scenario())

    def test_close_drops_pending_and_ignores_new_requests(self):
        async def scenario():
            render = SlowRender(duration=0.05)
            scheduler = RenderScheduler(render)
            scheduler.request()
            await asyncio.sleep(0.01)
            scheduler.request()
            scheduler.close()
            scheduler.request()
            await asyncio.sleep(0.1)
            return render, scheduler
        render, scheduler = run(scenario())
        assert render.calls == [False]
        assert not scheduler.busy
