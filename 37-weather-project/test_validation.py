import unittest
from pipeline import validate_daily

class ValidationTest(unittest.TestCase):
    def test_valid_and_invalid_observations(self):
        data={"time":["2026-09-01"],"temperature_2m_max":[20],"temperature_2m_min":[10],"precipitation_sum":[0]}
        self.assertEqual(len(validate_daily(data)),1)
        for high,low,rain in [(5,10,0),(20,10,-1),(None,10,0),(float('nan'),10,0)]:
            broken=dict(data,temperature_2m_max=[high],temperature_2m_min=[low],precipitation_sum=[rain])
            with self.assertRaises(ValueError): validate_daily(broken)
        with self.assertRaises(ValueError): validate_daily(dict(data,time=[]))

if __name__ == '__main__': unittest.main()
