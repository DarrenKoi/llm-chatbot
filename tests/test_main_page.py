def test_main_page_renders_sample_template(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Signal Room" in response.data
    assert b"Server Status" in response.data
