# __init__.py — ne publie que le Dashboard comme plugin MO2

from .StartupDashboard import StartupDashboard
__all__ = ["StartupDashboard"]

def createPlugin():
    # MO2 chargera uniquement ce plugin
    return StartupDashboard()

# (Optionnel) si ton MO2 appelle createPlugins(), on renvoie une liste à un seul élément
def createPlugins():
    return [StartupDashboard()]
