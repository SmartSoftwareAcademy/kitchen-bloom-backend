def get_request_branch_id(request):
    """
    Extract branch id from request headers, query params, or POST data.
    Priority: x-branch-id header > HTTP_X_BRANCH_ID > query param > POST data
    """
    return (
        request.headers.get('x-branch-id')
        or request.META.get('HTTP_X_BRANCH_ID')
        or request.query_params.get('branch_id')
        or request.data.get('branch_id')
    ) 