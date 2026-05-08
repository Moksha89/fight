
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apiManager.base.views import *
from apiManager.userManager.views import *
from apiManager.wallet.views import *
# Lottery: keep code in apiManager/lotteryManager & lotteryManager; enable by uncommenting below and adding to INSTALLED_APPS
# from apiManager.lotteryManager.views import *
from apiManager.cockfightManager.views import *
from apiManager.dicePlayManager.views import *


baseRouter = DefaultRouter()
baseRouter.register(r'settings', SettingViewSet, basename='settings')
baseRouter.register(r'statuses', StatusViewSet, basename='status')
baseRouter.register(r'products', ProductViewSet, basename='products')
baseRouter.register(r'product-order', ProductOrderViewSet,
                    basename='product-order')
baseRouter.register(r'banners', BannerViewSet, basename='banners')
baseRouter.register(r'highlights', HighlightViewSet, basename='highlights')
baseRouter.register(r'learningvideos', LearningVideoViewSet,
                    basename='learning-videos')


userManagerRouter = DefaultRouter()
userManagerRouter.register(r'', UserViewSet, basename='user')
userManagerRouter.register(
    r'subscription', SubscriptionViewSet, basename='subscription')


walletRouter = DefaultRouter()
walletRouter.register(r'me', WalletViewSet, basename='wallet')
walletRouter.register(r'deposit', DepositRequestViewSet,
                      basename='deposit-request')
walletRouter.register(r'withdrawal', WithdrawalRequestViewSet,
                      basename='withdrawal-request')    


# lotteryRouter = DefaultRouter()
# lotteryRouter.register(r'gift-pools', GiftPoolViewSet, basename='giftpool')
# lotteryRouter.register(r'price-pools', PricePoolRangeViewSet, basename='price-pool-range')

cockfightRouter = DefaultRouter()
cockfightRouter.register(
    r'bets', CockfightMatchBetViewSet, basename='cockfight-bets')
cockfightRouter.register(
    r'auto-history', CockfightAutoMatchViewSet, basename='cockfight-auto-history')
cockfightRouter.register(
    r'manual-history', ZoneViewSet, basename='cockfight-manual-history')
cockfightRouter.register(
    r'odds', OddsViewSet, basename='cockfight-odds')


dicePlayRouter = DefaultRouter()
dicePlayRouter.register(r'history', BoardViewSet, basename='dice-history')
dicePlayRouter.register(r'bets', DicePlayMatchBetViewSet, basename='dice-bets')


urlpatterns = [
    path('base/', include(baseRouter.urls)),
    path('user/', include(userManagerRouter.urls)),
    path('wallet/', include(walletRouter.urls)),
    path('cockfight/', include(cockfightRouter.urls)),
    path('dice-play/', include(dicePlayRouter.urls)),
    # path('lottery/', include(lotteryRouter.urls)),
]
