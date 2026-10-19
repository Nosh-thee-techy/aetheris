"""Attester jobs for the frozen Nyando rule.

Rainfall reads CHIRPS on Earth Engine. Radar signs only a Sentinel-1 RTC
fraction that clears the frozen prior. Neither job downloads an Africa-wide
CHIRPS file, and neither job signs when the rule does not fire.
"""
