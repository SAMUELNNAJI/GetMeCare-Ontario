from django.core.management.base import BaseCommand
from Chatbot.models import SiteKnowledge


class Command(BaseCommand):
    help = 'Populate site knowledge base with GetMeCare information'

    def handle(self, *args, **options):
        knowledge_data = [
            {
                'category': 'Services',
                'question': 'What services do you offer?',
                'answer': 'GetMeCare Ontario offers various caregiving services including Personal Support Worker (PSW) care, In-Home Senior Care, Postpartum Caregiver & Newborn care, and Companionship services. All our caregivers are pre-vetted and verified.',
                'keywords': 'services, offer, provide, care, caregiving, psw, personal support worker',
                'priority': 10
            },
            {
                'category': 'Services',
                'question': 'What is a Personal Support Worker?',
                'answer': 'A Personal Support Worker (PSW) is a certified healthcare professional who provides hands-on daily care including bathing, grooming, medication reminders, and personal care for seniors and adults in need.',
                'keywords': 'psw, personal support worker, certified, healthcare, daily care',
                'priority': 9
            },
            {
                'category': 'Services',
                'question': 'Do you offer senior care?',
                'answer': 'Yes, we offer specialized In-Home Senior Care provided by compassionate PSWs. This includes companionship, mobility assistance, personal hygiene support, and daily living assistance for aging parents.',
                'keywords': 'senior, elderly, aging, elderly care, senior care, in-home',
                'priority': 9
            },
            {
                'category': 'Services',
                'question': 'Do you offer postpartum care?',
                'answer': 'Yes, we have trained Postpartum Caregivers who support new mothers with baby care, feeding assistance, light household tasks, and newborn care after delivery.',
                'keywords': 'postpartum, newborn, baby, mother, delivery, post-delivery',
                'priority': 8
            },
            {
                'category': 'How It Works',
                'question': 'How does GetMeCare work?',
                'answer': 'GetMeCare connects Ontario families with pre-vetted independent PSWs and caregivers. Families can browse caregivers, view profiles, and hire directly. Our platform provides admin-mediated scheduling, payment processing, and ongoing support throughout the caregiving relationship.',
                'keywords': 'how, work, process, platform, hire, connect',
                'priority': 10
            },
            {
                'category': 'How It Works',
                'question': 'How do I find a caregiver?',
                'answer': 'You can find a caregiver by browsing our verified caregivers list, filtering by location and skills, and reviewing profiles. Once you find a suitable caregiver, you can contact them through our platform to discuss your care needs.',
                'keywords': 'find, search, browse, caregiver, look for',
                'priority': 10
            },
            {
                'category': 'How It Works',
                'question': 'How do I hire a caregiver?',
                'answer': 'After finding a caregiver that matches your needs, you can contact them through our platform. Our admin team will help coordinate the scheduling, and all payments are processed securely through our system with caregiver earning 85% of the hourly rate.',
                'keywords': 'hire, employ, pay, payment, schedule, booking',
                'priority': 9
            },
            {
                'category': 'Pricing',
                'question': 'How much does it cost?',
                'answer': 'Our caregivers set their own hourly rates, with an average of $31.50 per hour. Caregivers earn 85% of the hourly rate, while 15% covers platform fees and admin services. Families pay caregivers directly through our secure platform.',
                'keywords': 'cost, price, rate, hourly, expensive, cheap, afford',
                'priority': 9
            },
            {
                'category': 'Pricing',
                'question': 'What is the average hourly rate?',
                'answer': 'The average hourly rate for caregivers on our platform is $31.50 per hour. Rates vary based on caregiver experience, skills, and location. Each caregiver sets their own rate, which is displayed on their profile.',
                'keywords': 'average, rate, hourly, price, typical',
                'priority': 8
            },
            {
                'category': 'Safety',
                'question': 'Are caregivers verified?',
                'answer': 'Yes, all caregivers on our platform undergo a thorough verification process including ID verification, Vulnerable Sector Check (VSC), PSW certificate validation, and credential confirmation by our admin team.',
                'keywords': 'verified, vetted, background check, safe, safety, security, vetting',
                'priority': 10
            },
            {
                'category': 'Safety',
                'question': 'What background checks do you perform?',
                'answer': 'We require caregivers to submit PSW certificates, Vulnerable Sector Checks, government ID, First Aid/CPR certificates, and resumes. Our admin team reviews and verifies all documents before approving caregivers.',
                'keywords': 'background check, documents, verification, certificate, vsc, vulnerable sector',
                'priority': 9
            },
            {
                'category': 'Coverage',
                'question': 'What areas do you serve?',
                'answer': 'GetMeCare Ontario serves all Ontario municipalities including Toronto, Ottawa, Hamilton, Mississauga, Brampton, London, Windsor, Kitchener, Waterloo, and many more cities across the province.',
                'keywords': 'area, location, city, serve, coverage, region, ontario, toronto',
                'priority': 9
            },
            {
                'category': 'Coverage',
                'question': 'Do you serve Toronto?',
                'answer': 'Yes, we serve Toronto and the Greater Toronto Area (GTA) including Mississauga, Brampton, Markham, Vaughan, and surrounding areas. We have many verified caregivers available in the Toronto region.',
                'keywords': 'toronto, gta, greater toronto, mississauga, brampton',
                'priority': 8
            },
            {
                'category': 'For Caregivers',
                'question': 'How do I apply as a caregiver?',
                'answer': 'Caregivers can apply by creating an account, completing their profile, submitting required documents (PSW certificate, VSC, government ID, etc.), and waiting for admin approval. Once approved, caregivers can set their hourly rate and start receiving job requests.',
                'keywords': 'apply, caregiver, join, sign up, register, psw',
                'priority': 9
            },
            {
                'category': 'For Caregivers',
                'question': 'What documents do I need to apply?',
                'answer': 'To apply as a caregiver, you need: PSW Certificate, Vulnerable Sector Check, Government ID, First Aid/CPR Certificate, and Resume/CV. Additional documents may be requested during the review process.',
                'keywords': 'documents, apply, caregiver, certificate, vsc, id, resume',
                'priority': 8
            },
            {
                'category': 'Support',
                'question': 'How do I contact support?',
                'answer': 'You can contact our support team through the Contact Us page on our website. Our admin team is available to help with any questions about finding caregivers, hiring, payments, or technical issues.',
                'keywords': 'contact, support, help, assist, question, issue',
                'priority': 8
            },
            {
                'category': 'Support',
                'question': 'What if I have a problem with my caregiver?',
                'answer': 'If you experience any issues with your caregiver, please contact our admin team immediately. We mediate all caregiver-employer relationships and can help resolve disputes, provide replacement caregivers, or address any concerns.',
                'keywords': 'problem, issue, dispute, conflict, complaint, replace',
                'priority': 9
            },
            {
                'category': 'Platform',
                'question': 'What is GetMeCare?',
                'answer': 'GetMeCare Ontario is a platform that connects families with trusted, pre-vetted independent Personal Support Workers. We provide a mediated, transparent, and safe marketplace for finding quality care while allowing families to pay caregivers directly.',
                'keywords': 'getmecare, about, platform, company, business',
                'priority': 10
            },
            {
                'category': 'Platform',
                'question': 'Is GetMeCare available outside Ontario?',
                'answer': 'Currently, GetMeCare focuses exclusively on serving Ontario municipalities. We do not provide services outside of Ontario at this time.',
                'keywords': 'ontario, outside, province, other, expand',
                'priority': 7
            },
            {
                'category': 'Payment',
                'question': 'How do payments work?',
                'answer': 'Payments are processed securely through our platform. Families pay the agreed hourly rate, and caregivers receive 85% of that amount. The remaining 15% covers platform fees and admin services. All payments are tracked and managed through our system.',
                'keywords': 'payment, pay, money, fee, percentage, 85, 15',
                'priority': 9
            },
            {
                'category': 'Scheduling',
                'question': 'How does scheduling work?',
                'answer': 'Our admin team helps coordinate scheduling between families and caregivers. Once you agree on care needs, shifts are created with specific dates and times. Caregivers can clock in and out through the platform, and all hours are tracked for payment processing.',
                'keywords': 'schedule, shift, time, booking, coordination',
                'priority': 8
            },
            {
                'category': 'Caregiver Skills',
                'question': 'What skills do caregivers have?',
                'answer': 'Our caregivers have various skills including personal care, senior care, dementia care, mobility assistance, medication management, companionship, postpartum care, cooking, and light housekeeping. Each caregiver lists their specific skills on their profile.',
                'keywords': 'skills, abilities, qualifications, experience, training',
                'priority': 8
            },
            {
                'category': 'Caregiver Skills',
                'question': 'Do you have caregivers with dementia experience?',
                'answer': 'Yes, many of our caregivers have experience with dementia and Alzheimer\'s care. You can filter caregivers by specific skills including dementia care when browsing our platform.',
                'keywords': 'dementia, alzheimer, memory, experience, specialized',
                'priority': 8
            },
        ]

        created_count = 0
        updated_count = 0

        for item in knowledge_data:
            knowledge, created = SiteKnowledge.objects.get_or_create(
                question=item['question'],
                defaults={
                    'category': item['category'],
                    'answer': item['answer'],
                    'keywords': item['keywords'],
                    'priority': item['priority']
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {item["question"]}'))
            else:
                # Update existing record
                knowledge.category = item['category']
                knowledge.answer = item['answer']
                knowledge.keywords = item['keywords']
                knowledge.priority = item['priority']
                knowledge.save()
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated: {item["question"]}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully populated site knowledge: {created_count} created, {updated_count} updated'
            )
        )