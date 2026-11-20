import httpx

r = httpx.post('http://127.0.0.1:8003/api/v1/auth/login', json={'email':'owner@acme.com','password':'any'})
tok = r.json()['access_token']
hdrs = {'Authorization': 'Bearer ' + tok}

doc = "Q3 2026 Financial Report\nMarketing budget: 70000, actual: 85000 (overspend 21.4%)\nRevenue: 310000, net margin: 18.7%"
files = {'file': ('q3.txt', doc, 'text/plain')}
httpx.post('http://127.0.0.1:8003/api/v1/documents/upload', headers=hdrs, files=files)

tests = [
    ('cricket-off-topic', 'What is the best cricket team?'),
    ('recipe-off-topic',  'Give me a pasta recipe'),
    ('marketing-budget',  'Did we overspend on marketing this quarter?'),
    ('forecast',          'Forecast our revenue for the next 3 months'),
    ('risk',              'What are our financial risk flags?'),
]

for label, q in tests:
    r2 = httpx.post('http://127.0.0.1:8003/api/v1/advisor/ask', headers=hdrs,
                    json={'query': q, 'extracted_params': {}}, timeout=30)
    d = r2.json()
    print('[' + label + '] intent=' + d['intent'] + ' route=' + d['route'])
    print('  citations: ' + str(d.get('citations', [])))
    print('  answer: ' + d['answer'][:220])
    print()
