"""Frame-rate independent motion; no GTK or hardware dependencies."""
from dataclasses import dataclass
import math

INSTANT = 90
FAST = 150
NORMAL = 240
SLOW = 380
PRESS_SCALE = .98
AMBIENT = 6000
SPRING_FREQUENCY = 24.0
SPRING_DAMPING = .90

@dataclass
class Spring:
    value: float
    velocity: float = 0.0
    target: float = 0.0

    def step(self, dt):
        # Exact underdamped solution: retargeting keeps both position and velocity.
        w = SPRING_FREQUENCY
        z = SPRING_DAMPING
        wd = w * math.sqrt(1-z*z)
        x = self.value-self.target
        b = (self.velocity+z*w*x)/wd
        decay = math.exp(-z*w*dt)
        c, s = math.cos(wd*dt), math.sin(wd*dt)
        self.value = self.target+decay*(x*c+b*s)
        self.velocity = decay*((-z*w*x+wd*b)*c+(-z*w*b-wd*x)*s)
        if abs(self.value-self.target) < .0001 and abs(self.velocity) < .001:
            self.value, self.velocity = self.target, 0.0
        return self.value


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t*t*t*(t*(t*6-15)+10)
