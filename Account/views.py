from django.shortcuts import render

# Create your views here.

def login_view(request):
    return render(request, 'Account/login.html')


def signup(request):
    return render(request, 'Account/signup.html')


def admin_dashboard(request):
    return render(request, 'Account/admin-dashboard.html')


def employer_dashboard(request):
    return render(request, 'Account/employer-dashboard.html')


def caregiver_dashboard(request):
    return render(request, 'Account/caregiver-dashboard.html')

