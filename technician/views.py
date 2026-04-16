from django.shortcuts import render, redirect
from django.contrib import messages
from functools import wraps

SAMPLE_JOBS = [
    {
        'id': 1, 'time': '8:00 AM', 'status': 'completed',
        'customer': 'Riverside Auto Wash',
        'address': '1234 Riverside Ave, Jacksonville, FL 32204',
        'contact': 'Mike Johnson', 'phone': '(904) 555-0142',
        'device_type': 'RPZ', 'device_size': '1"',
        'device_make': 'Watts', 'device_model': '009', 'serial': 'W2204-8871',
        'device_notes': 'Behind fence, NE corner of building',
        'lat': 30.3149, 'lng': -81.6693,
        'device_lat': 30.31498, 'device_lng': -81.66915,
    },
    {
        'id': 2, 'time': '9:15 AM', 'status': 'completed',
        'customer': 'Sunshine Apartments',
        'address': '567 Park St, Jacksonville, FL 32204',
        'contact': 'Sandra Lee', 'phone': '(904) 555-0198',
        'device_type': 'DCVA', 'device_size': '3/4"',
        'device_make': 'Febco', 'device_model': '850', 'serial': 'F2019-3341',
        'device_notes': 'Utility room, ground floor, west wing',
        'lat': 30.3220, 'lng': -81.6580,
        'device_lat': 30.32208, 'device_lng': -81.65785,
    },
    {
        'id': 3, 'time': '10:30 AM', 'status': 'in_progress',
        'customer': 'Orange Park Commons HOA',
        'address': '890 Blanding Blvd, Orange Park, FL 32065',
        'contact': 'Tom Rivera', 'phone': '(904) 555-0211',
        'device_type': 'RPZ', 'device_size': '2"',
        'device_make': 'Wilkins', 'device_model': '975XL', 'serial': 'WK2021-6612',
        'device_notes': 'Irrigation backflow, behind clubhouse',
        'lat': 30.1654, 'lng': -81.7065,
        'device_lat': 30.16550, 'device_lng': -81.70635,
    },
    {
        'id': 4, 'time': '11:45 AM', 'status': 'pending',
        'customer': 'Fleming Island Medical Center',
        'address': '234 Town Center Blvd, Fleming Island, FL 32003',
        'contact': 'Dr. Patricia Holt', 'phone': '(904) 555-0334',
        'device_type': 'RPZ', 'device_size': '1.5"',
        'device_make': 'Ames', 'device_model': '4000SS', 'serial': 'A2022-1197',
        'device_notes': 'Mechanical room, lower level, south entrance',
        'lat': 30.1010, 'lng': -81.7143,
        'device_lat': 30.10108, 'device_lng': -81.71415,
    },
    {
        'id': 5, 'time': '1:00 PM', 'status': 'pending',
        'customer': 'St. Johns County Recreation Center',
        'address': '456 Race Track Rd, St. Johns, FL 32259',
        'contact': 'Gary Simmons', 'phone': '(904) 555-0455',
        'device_type': 'PVB', 'device_size': '1"',
        'device_make': 'Watts', 'device_model': '800M4', 'serial': 'W2020-5589',
        'device_notes': 'Exterior, east side of building near irrigation valve box',
        'lat': 30.1580, 'lng': -81.6043,
        'device_lat': 30.15808, 'device_lng': -81.60415,
    },
    {
        'id': 6, 'time': '2:00 PM', 'status': 'pending',
        'customer': 'Ponte Vedra Beach Club',
        'address': '789 A1A N, Ponte Vedra Beach, FL 32082',
        'contact': 'Claire Ashford', 'phone': '(904) 555-0567',
        'device_type': 'DCVA', 'device_size': '1"',
        'device_make': 'Febco', 'device_model': '860', 'serial': 'F2023-8823',
        'device_notes': 'Pool equipment room, north end of clubhouse',
        'lat': 30.2394, 'lng': -81.3883,
        'device_lat': 30.23948, 'device_lng': -81.38815,
    },
    {
        'id': 7, 'time': '3:00 PM', 'status': 'pending',
        'customer': 'Atlantic Beach City Hall',
        'address': '800 Seminole Rd, Atlantic Beach, FL 32233',
        'contact': 'Derrick Fowler', 'phone': '(904) 555-0688',
        'device_type': 'RPZ', 'device_size': '1"',
        'device_make': 'Watts', 'device_model': '909', 'serial': 'W2021-2214',
        'device_notes': 'Exterior east wall, padlocked enclosure',
        'lat': 30.3371, 'lng': -81.3996,
        'device_lat': 30.33718, 'device_lng': -81.39945,
    },
    {
        'id': 8, 'time': '3:45 PM', 'status': 'pending',
        'customer': 'Neptune Beach HOA',
        'address': '123 Neptune Ave, Neptune Beach, FL 32266',
        'contact': 'Beth Calloway', 'phone': '(904) 555-0712',
        'device_type': 'PVB', 'device_size': '3/4"',
        'device_make': 'Wilkins', 'device_model': '720A', 'serial': 'WK2019-9901',
        'device_notes': 'Irrigation system, near front entrance sign',
        'lat': 30.3127, 'lng': -81.4027,
        'device_lat': 30.31278, 'device_lng': -81.40255,
    },
    {
        'id': 9, 'time': '4:30 PM', 'status': 'pending',
        'customer': 'Mandarin Presbyterian Church',
        'address': '11946 Mandarin Rd, Jacksonville, FL 32223',
        'contact': 'Pastor Dale Norris', 'phone': '(904) 555-0834',
        'device_type': 'DCVA', 'device_size': '3/4"',
        'device_make': 'Ames', 'device_model': '2000SS', 'serial': 'A2020-7743',
        'device_notes': 'Exterior south side, irrigation backflow near garden beds',
        'lat': 30.1580, 'lng': -81.6243,
        'device_lat': 30.15808, 'device_lng': -81.62415,
    },
    {
        'id': 10, 'time': '5:15 PM', 'status': 'pending',
        'customer': 'Baymeadows Plaza',
        'address': '8550 Baymeadows Rd, Jacksonville, FL 32256',
        'contact': 'Lisa Crane', 'phone': '(904) 555-0956',
        'device_type': 'RPZ', 'device_size': '2"',
        'device_make': 'Febco', 'device_model': '880V', 'serial': 'F2022-4456',
        'device_notes': 'Loading dock utility room, rear of building',
        'lat': 30.2347, 'lng': -81.5513,
        'device_lat': 30.23478, 'device_lng': -81.55115,
    },
]


def tech_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('tech_logged_in'):
            return redirect('tech_login')
        return view_func(request, *args, **kwargs)
    return wrapper


def tech_login(request):
    if request.session.get('tech_logged_in'):
        return redirect('tech_dashboard')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        if username == 'test' and password == 'test':
            request.session['tech_logged_in'] = True
            request.session['tech_name'] = 'Test Technician'
            return redirect('tech_dashboard')
        error = 'Invalid username or password.'
    return render(request, 'technician/login.html', {'error': error})


def tech_logout(request):
    request.session.flush()
    return redirect('tech_login')


@tech_required
def tech_dashboard(request):
    completed = sum(1 for j in SAMPLE_JOBS if j['status'] == 'completed')
    in_progress = sum(1 for j in SAMPLE_JOBS if j['status'] == 'in_progress')
    pending = sum(1 for j in SAMPLE_JOBS if j['status'] == 'pending')
    return render(request, 'technician/dashboard.html', {
        'jobs': SAMPLE_JOBS,
        'completed': completed,
        'in_progress': in_progress,
        'pending': pending,
        'total': len(SAMPLE_JOBS),
        'tech_name': request.session.get('tech_name', 'Technician'),
    })


@tech_required
def tech_job_detail(request, job_id):
    job = next((j for j in SAMPLE_JOBS if j['id'] == job_id), None)
    if not job:
        return redirect('tech_dashboard')
    submitted = False
    if request.method == 'POST':
        submitted = True
    return render(request, 'technician/job_detail.html', {
        'job': job,
        'submitted': submitted,
        'tech_name': request.session.get('tech_name', 'Technician'),
    })
