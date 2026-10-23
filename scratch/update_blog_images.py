"""
Update all 30 blog posts with tailored, highly relevant images that match their specific title.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GETMECARE.settings')
django.setup()

from AdminApp.models import BlogPost

IMAGE_UPDATES = {
    # 1. Choose Right PSW
    "how-to-choose-the-right-psw-in-ontario": {
        "url": "https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?w=1200&auto=format&fit=crop&q=80",
        "alt": "Personal Support Worker providing compassionate one-on-one care to senior in Ontario"
    },
    # 2. Dementia In-Home Care
    "dementia-alzheimers-in-home-care-ontario": {
        "url": "https://images.unsplash.com/photo-1581579438747-1dc8d17bbce4?w=1200&auto=format&fit=crop&q=80",
        "alt": "Caregiver reassuring senior living with dementia through gentle memory engagement"
    },
    # 3. Tax Credits
    "ontario-caregiver-tax-credits-financial-relief": {
        "url": "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=1200&auto=format&fit=crop&q=80",
        "alt": "Canadian tax return forms and financial calculations for family caregiver credits"
    },
    # 4. Palliative Care
    "palliative-end-of-life-care-at-home-ontario": {
        "url": "https://images.unsplash.com/photo-1516585427167-9f4af9627e6c?w=1200&auto=format&fit=crop&q=80",
        "alt": "Gentle bedside palliative comfort care holding hands in Ontario home"
    },
    # 5. Post-Surgery Recovery
    "post-surgery-recovery-at-home-ontario": {
        "url": "https://images.unsplash.com/photo-1584515933487-779824d29309?w=1200&auto=format&fit=crop&q=80",
        "alt": "Caregiver assisting recovering post-surgery patient in bed at home"
    },
    # 6. Top-Earning Skills
    "top-earning-psw-skills-ontario": {
        "url": "https://images.unsplash.com/photo-1584467735871-8e85353a8413?w=1200&auto=format&fit=crop&q=80",
        "alt": "Professional Ontario Personal Support Worker in medical scrubs smiling confidently"
    },
    # 7. Burnout
    "preventing-caregiver-burnout-ontario": {
        "url": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=1200&auto=format&fit=crop&q=80",
        "alt": "Caregiver taking peaceful outdoor mindfulness break to prevent burnout"
    },
    # 8. First Shift Preparation
    "first-in-home-care-shift-checklist": {
        "url": "https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?w=1200&auto=format&fit=crop&q=80",
        "alt": "Caregiver organizing medical checklist and personal support equipment"
    },
    # 9. Employment Standards & PHIPA
    "patient-privacy-phipa-independent-caregivers-ontario": {
        "url": "https://images.unsplash.com/photo-1450133064473-71024230f91b?w=1200&auto=format&fit=crop&q=80",
        "alt": "Ontario healthcare legal regulations and PHIPA privacy compliance documents"
    },
    # 10. Alzheimer's De-escalation
    "dementia-behavior-de-escalation-toolkit": {
        "url": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=1200&auto=format&fit=crop&q=80",
        "alt": "Caregiver practicing gentle verbal de-escalation with Alzheimer's patient"
    },
    # 11. Medication Reminders
    "medication-reminder-best-practices-ontario-psws": {
        "url": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=1200&auto=format&fit=crop&q=80",
        "alt": "Senior blister pack dosette pill organizer and fresh water glass"
    },
    # 12. Caregiver Rights ESA
    "ontario-caregiver-rights-employment-standards-act-vs-contracting": {
        "url": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=1200&auto=format&fit=crop&q=80",
        "alt": "Legal scale of justice representing caregiver workplace rights under the Ontario ESA"
    },
    # 13. Safe Patient Transfers
    "safe-patient-transfers-hoyer-lift-ergonomics-ontario": {
        "url": "https://images.unsplash.com/photo-1573497620053-ea5300f94f21?w=1200&auto=format&fit=crop&q=80",
        "alt": "Ergonomic patient transfer assistance with mechanical mobility support"
    },
    # 14. Hospital Discharge Checklist
    "ontario-hospital-discharge-home-care-checklist": {
        "url": "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=1200&auto=format&fit=crop&q=80",
        "alt": "Senior hospital discharge corridor and transition to home care"
    },
    # 15. Trillium & ADP Funding
    "trillium-drug-program-adp-ontario-funding-guide": {
        "url": "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=1200&auto=format&fit=crop&q=80",
        "alt": "Doctor consulting patient on Trillium Drug Program and assistive device funding"
    },
    # 16. Overnight vs Live-in Care
    "overnight-vs-live-in-care-ontario-comparison": {
        "url": "https://images.unsplash.com/photo-1540518614846-7ede433c4ef0?w=1200&auto=format&fit=crop&q=80",
        "alt": "Quiet, comfortable bedroom setting for overnight senior home care"
    },
    # 17. Fall Prevention Checklist
    "fall-prevention-home-modification-checklist-ontario": {
        "url": "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?w=1200&auto=format&fit=crop&q=80",
        "alt": "Senior-accessible bathroom with wall-mounted safety grab bars and walk-in shower"
    },
    # 18. Palliative Care Support
    "palliative-end-of-life-home-care-ontario": {
        "url": "https://images.unsplash.com/photo-1518495973542-4542c06a5843?w=1200&auto=format&fit=crop&q=80",
        "alt": "Serene sunlight illuminating peaceful home environment for palliative care"
    },
    # 19. Police VSC Check
    "vetting-caregiver-vulnerable-sector-check-ontario": {
        "url": "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=1200&auto=format&fit=crop&q=80",
        "alt": "Thorough background check and police record verification screening"
    },
    # 20. Elder Nutrition & Hydration
    "elder-nutrition-hydration-meal-prep-ontario-psw": {
        "url": "https://images.unsplash.com/photo-1498837167922-ddd27525d352?w=1200&auto=format&fit=crop&q=80",
        "alt": "Freshly prepared nutritious elder meal with balanced vegetables and proteins"
    },
    # 21. Infection Control & PPE
    "infection-control-ppe-guidelines-ontario-home-care": {
        "url": "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?w=1200&auto=format&fit=crop&q=80",
        "alt": "Medical examination gloves and infection control sanitization equipment"
    },
    # 22. Power of Attorney
    "power-of-attorney-personal-care-vs-property-ontario": {
        "url": "https://images.unsplash.com/photo-1450133064473-71024230f91b?w=1200&auto=format&fit=crop&q=80",
        "alt": "Signing legal Power of Attorney document with fountain pen"
    },
    # 23. Set Hourly Rates
    "how-to-set-competitive-psw-hourly-rates-ontario": {
        "url": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=1200&auto=format&fit=crop&q=80",
        "alt": "Calculator and financial rate card for independent PSW pricing in Ontario"
    },
    # 24. Signs Parent Needs Care
    "signs-aging-parent-needs-full-time-home-care-ontario": {
        "url": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=1200&auto=format&fit=crop&q=80",
        "alt": "Elderly parent sitting thoughtfully near living room window"
    },
    # 25. Respite Care Burnout
    "respite-care-ontario-families-preventing-burnout": {
        "url": "https://images.unsplash.com/photo-1544717305-2782549b5136?w=1200&auto=format&fit=crop&q=80",
        "alt": "Family caregiver finding peace and emotional relief through scheduled respite care"
    },
    # 26. CPR & First Aid
    "cpr-first-aid-recertification-guide-ontario": {
        "url": "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?w=1200&auto=format&fit=crop&q=80",
        "alt": "First aid training kit with CPR mask and resuscitation equipment"
    },
    # 27. Home Care vs LTC
    "private-home-care-vs-long-term-care-ontario-costs": {
        "url": "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=1200&auto=format&fit=crop&q=80",
        "alt": "Comfortable, warm private home environment compared with residential care"
    },
    # 28. Medical Emergencies 911 vs 811
    "medical-emergencies-at-home-when-to-call-911-ontario": {
        "url": "https://images.unsplash.com/photo-1587745416684-47953f16f02f?w=1200&auto=format&fit=crop&q=80",
        "alt": "Telephone keypad dialing emergency assistance for urgent healthcare needs"
    },
    # 29. Caregiver Contract
    "how-to-draft-private-caregiver-contract-ontario": {
        "url": "https://images.unsplash.com/photo-1521791136064-7986c2920216?w=1200&auto=format&fit=crop&q=80",
        "alt": "Family and caregiver shaking hands over signed home care agreement"
    },
    # 30. Night Shifts PSW
    "managing-night-shifts-in-home-psw-ontario": {
        "url": "https://images.unsplash.com/photo-1518241353330-0f7941c2d9b5?w=1200&auto=format&fit=crop&q=80",
        "alt": "Quiet, focused night shift desk setting with warm lamp and hot tea"
    },
}

updated = 0
for post in BlogPost.objects.all():
    match = IMAGE_UPDATES.get(post.slug)
    if match:
        post.featured_image_url = match["url"]
        post.image_alt = match["alt"]
        post.save(update_fields=['featured_image_url', 'image_alt'])
        updated += 1
        print(f"Updated post #{post.id}: {post.title[:50]}...")
    else:
        print(f"No specific mapping for slug: {post.slug}")

print(f"\nDone! Successfully updated {updated} blog posts with topic-specific images.")
