import httpx
import respx

BASE_URL = "https://webapis.schoolcafe.com/api"


class TestSchoolsAPI:
    @respx.mock
    def test_search_schools(self, client, schoolcafe_fixture):
        districts = schoolcafe_fixture("search_districts")
        schools = schoolcafe_fixture("search_schools")

        respx.get(f"{BASE_URL}/GetISDByShortName").mock(
            return_value=httpx.Response(200, json=districts)
        )
        respx.get(f"{BASE_URL}/GetSchoolsList").mock(
            return_value=httpx.Response(200, json=schools)
        )

        response = client.get("/api/schools", params={"q": "springfield"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["school_id"] == "school-001"

    @respx.mock
    def test_search_empty_query(self, client):
        respx.get(f"{BASE_URL}/GetISDByShortName").mock(
            return_value=httpx.Response(200, json=[])
        )

        response = client.get("/api/schools", params={"q": ""})
        assert response.status_code == 200
        assert response.json() == []

    @respx.mock
    def test_schoolcafe_down(self, client):
        respx.get(f"{BASE_URL}/GetISDByShortName").mock(
            return_value=httpx.Response(500)
        )

        response = client.get("/api/schools", params={"q": "test"})
        assert response.status_code == 500
