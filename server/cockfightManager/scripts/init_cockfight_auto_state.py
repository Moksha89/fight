from cockfightManager.models import AutoMatchPollingState

def run():
        state, _ = AutoMatchPollingState.objects.get_or_create(id=1)

        state.runningAutoMatchId = None
        state.runningMatchRefId = None
        state.matchNumber = None
        state.isNewMatchUpdated = None
        state.isAcceptingBet = False
        state.liveUrl = None
        state.save()

        print("Cockfight Auto State Set.")
