
def run():
    
    import requests
    base_url = "https://api.open-elevation.com/api/v1/lookup" #"http://overpass-api.de/api/interpreter"

    all_locations = [(10,10),(20,20),(41.161758,-8.583933)]
    loc_str = ""
    for i, l in enumerate(all_locations):
        if i==0:
            loc_str += f"?locations={l[0]},{l[1]}"
        else:
            loc_str += f"|{l[0]},{l[1]}"
    overpass_url = base_url + loc_str
    print(overpass_url)
    response = requests.get(overpass_url)
    data = response.json()
    elevations = [ r['elevation'] for r in data['results']]
    print(elevations)

    #######################################
    payload = '''{
	"locations":
	[
		{
			"latitude": 10,
			"longitude": 10
		},
		{
			"latitude":20,
			"longitude": 20
		},
		{
			"latitude":41.161758,
			"longitude":-8.583933
		}
	]

    }''' 
    r = requests.post(base_url, data = payload)
    data = response.json()
    print(data)
    elevations = [ r['elevation'] for r in data['results']]
    print(elevations)
    return

run()
exit()
