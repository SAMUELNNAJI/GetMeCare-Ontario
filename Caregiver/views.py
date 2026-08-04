from django.shortcuts import render


def home(request):
    return render(request, 'Caregiver/index.html')


def browse(request):
    return render(request, 'Caregiver/browse.html')


def how_it_works(request):
    return render(request, 'Caregiver/how_it_works.html')


def services(request):
    return render(request, 'Caregiver/services.html')


def contact(request):
    return render(request, 'Caregiver/contact.html')


def privacy(request):
    return render(request, 'Caregiver/privacy.html')


def terms(request):
    return render(request, 'Caregiver/terms.html')


