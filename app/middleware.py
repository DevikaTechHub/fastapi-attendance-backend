import time

from fastapi import Request


# Middleware function
async def log_requests(
    request: Request,
    call_next
):

    start_time = time.time()

    # Process request
    response = await call_next(request)

    end_time = time.time()

    process_time = end_time - start_time

    print(
        f"{request.method} {request.url} completed in {process_time:.4f} seconds"
    )

    return response