from django.shortcuts import render, redirect
from django.contrib import messages


def home(request):
    return render(request, "public/home.html")


def services(request):
    return render(request, "public/services.html")


def coverage(request):
    return render(request, "public/coverage.html")


def contact(request):
    if request.method == "POST":
        messages.success(request, "Thank you! We'll be in touch within one business day.")
        return redirect("contact")
    return render(request, "public/contact.html")
