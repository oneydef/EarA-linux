import unittest
from eara.motion_physics import Spring, smooth

class MotionPhysicsTests(unittest.TestCase):
    def test_spring_retarget_preserves_velocity(self):
        s=Spring(0,target=1)
        s.step(.07)
        before=(s.value,s.velocity)
        s.target=0
        self.assertEqual((s.value,s.velocity),before)
        for _ in range(180):s.step(1/60)
        self.assertEqual((s.value,s.velocity),(0,0))

    def test_spring_independent_of_frame_rate(self):
        a,b=Spring(0,target=1),Spring(0,target=1)
        for _ in range(12):a.step(1/60)
        for _ in range(24):b.step(1/120)
        self.assertAlmostEqual(a.value,b.value,places=10)
        self.assertAlmostEqual(a.velocity,b.velocity,places=10)

    def test_smooth_is_bounded_and_monotonic(self):
        values=[smooth(i/100) for i in range(-5,106)]
        self.assertEqual(values,sorted(values))
        self.assertEqual((values[0],values[-1]),(0,1))
