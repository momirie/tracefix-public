from asgiref.sync import async_to_sync


def test_kwarg_named_like_main_wrap_params():
    @async_to_sync
    async def example(context=None, call_result=None, exc_info=None, task_context=None, awaitable=None):
        return (context, call_result, exc_info, task_context, awaitable)

    assert example(context=1) == (1, None, None, None, None)
    assert example(call_result=2, exc_info=3, task_context=4, awaitable=5) == (None, 2, 3, 4, 5)
