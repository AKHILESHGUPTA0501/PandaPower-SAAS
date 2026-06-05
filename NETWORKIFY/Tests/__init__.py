"""
Test suite for PowerSys SaaS.

Run with:
    pytest Tests/ -v
    pytest Tests/ --cov=. --cov-report=term-missing

Layout
------
  conftest.py            : shared fixtures (app, db, client, auth helpers)
  test_auth.py           : register / login / token / password reset
  test_users.py          : user CRUD, admin gates
  test_networks.py       : PowerNetwork + element CRUD
  test_substations.py    : Substation CRUD, geo search
  test_facilities.py     : Facility + feasibility study creation
  test_analyses.py       : analysis job dispatch
  test_reports.py        : report generation queueing
  test_feasibility.py    : FeasibilityService logic (pure unit)
  test_load_flow.py      : LoadFlowService on IEEE test cases
  test_short_circuit.py  : ShortCircuitService on IEEE test cases
  test_geo_service.py    : Haversine / bounding-box maths
  test_factory_presets.py: profile + preset lookups
  test_schemas.py        : Marshmallow validation rules
"""
