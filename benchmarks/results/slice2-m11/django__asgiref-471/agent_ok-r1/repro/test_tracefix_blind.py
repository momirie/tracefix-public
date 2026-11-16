from asgiref.sync import async_to_sync


def test_async_to_sync_kwarg_names_match_internal_params():
    @async_to_sync
    async def example(context=None, call_result=None, exc_info=None, task_context=None):
        return (context, call_result, exc_info, task_context)

    assert example(context=1, call_result=2, exc_info=3, task_context=4) == (1, 2, 3, 4)
