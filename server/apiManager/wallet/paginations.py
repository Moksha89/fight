from rest_framework.pagination import PageNumberPagination

class WalletPagination(PageNumberPagination):
    page_size = 15
    page_query_param = 'page'