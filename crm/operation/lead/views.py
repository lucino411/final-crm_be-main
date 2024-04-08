from django.views.generic import TemplateView, ListView, DetailView, UpdateView, DeleteView
from django.views.generic.edit import FormView
from django.forms import inlineformset_factory
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.db.models import Count, Q, F
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.exceptions import ValidationError


from administration.userprofile.views import AgentRequiredMixin, AgentContextMixin
from configuration.country.models import Country
from operation.company.models import Company
from operation.contact.models import Contact
from operation.client.models import Client
from .models import Lead, LeadProduct, LeadTask
from .forms import LeadForm, LeadProductForm, LeadUpdateForm, LeadTaskCreateForm, LeadTaskUpdateForm

from operation.deal.models import Deal, DealProduct, DealTask  


LeadProductFormset = inlineformset_factory(Lead, LeadProduct, form=LeadProductForm, extra=0, can_delete=True)

def convert_lead_to_deal(request, organization_slug, pk):
    lead = get_object_or_404(Lead, id=pk)


    with transaction.atomic():

        # Obtener el Contact asociado con el Lead
        contact = lead.contact
        if contact:
            # Actualiza el Client con los mismos datos que Contact, si existe (primary_email)
            client, created = Client.objects.get_or_create(
                primary_email=contact.primary_email,
                defaults={
                    'first_name': contact.first_name,
                    'last_name': contact.last_name,
                    'title': contact.title,
                    'phone': contact.phone,
                    'mobile_phone': contact.mobile_phone,
                    'company': contact.company,
                    'country': contact.country,
                    'created_by': contact.created_by,
                    'last_modified_by': contact.last_modified_by,
                    'created_time': contact.created_time,
                    'modified_time': contact.modified_time,
                    'organization': contact.organization,
                    'erased': contact.erased
                }           
            )

            # Crea un nuevo Client con los datos de Contact, si no existe
            # Asigna el objeto Country por el campo code de Country
            country_code = contact.country.code
            country_instance = Country.objects.get(code=country_code)            
            if created:
                client.first_name=contact.first_name
                client.last_name=contact.last_name
                client.title=contact.title
                client.primary_email=contact.primary_email
                client.phone=contact.phone
                client.mobile_phone=contact.mobile_phone
                client.company=contact.company
                client.country=country_instance
                client.created_by=contact.created_by
                client.last_modified_by=contact.last_modified_by
                client.created_time=contact.created_time
                client.modified_time=contact.modified_time
                client.organization=contact.organization
                client.erased=contact.erased
                client.save()

        # Verificar si el Contact está asociado a más Leads
        if contact.contact_leads.count() > 1:
            # Marcar al Contact como cliente pero no eliminar
            contact.is_client = True
            contact.save()
        else:
            # Eliminar el Contact si solo está asociado a este Lead
            contact.delete()
        
        # Obtener la Company asociada con el Lead
        company = lead.company
        if company:
            company.is_client = True
            company.save()

        # Crear una instancia de Deal con los datos de Lead
        deal = Deal(
            deal_name = lead.lead_name,
            deal_source=lead.lead_source,

            client=client,  # Asignar el Client aquí
            primary_email = lead.primary_email,
            first_name = lead.first_name,
            last_name = lead.last_name,            
            title=lead.title,
            phone=lead.phone,
            mobile_phone=lead.mobile_phone,

            company = lead.company,
            company_name=lead.company_name,
            company_email=lead.company_email,
            company_phone=lead.company_phone,
            website=lead.website,
            industry=lead.industry,

            country = lead.country,     
            currency = lead.currency,

            description=lead.description,

            assigned_to = lead.assigned_to,
            created_by = lead.created_by,
            last_modified_by = lead.last_modified_by,

            created_time = lead.created_time,
            modified_time = lead.modified_time,
            start_date_time = lead.start_date_time,
            end_date_time = lead.end_date_time,
            extended_end_date_time = lead.extended_end_date_time,
            actual_completion_date = lead.actual_completion_date,

            organization = lead.organization,
            
            stage = lead.stage,
            is_closed = lead.is_closed,
            erased=lead.erased,
        )
        deal.save()


        # Dentro de la transacción, después de crear el Deal
        deal_product_mapping = {}
        for lead_product in lead.lead_product.all():
            deal_product = DealProduct.objects.create(
                deal=deal,
                product=lead_product.product,
                cotizacion_url=lead_product.cotizacion_url
            )
            deal_product_mapping[lead_product] = deal_product

        deal_task_mapping = {}
        for lead_task in lead.lead_leadtask.all():
            deal_task = DealTask.objects.create(
                deal=deal,
                name=lead_task.name,
                deal_product=deal_product_mapping.get(lead_task.lead_product),
                # No asignar parent_task todavía
                description=lead_task.description,
                created_by=lead_task.created_by,
                created_time=lead_task.created_time,
                modified_time=lead_task.modified_time,
                assigned_to=lead_task.assigned_to,
                last_modified_by=lead_task.last_modified_by,
                organization=lead_task.organization,
                stage=lead_task.stage,
                is_closed=lead_task.is_closed,
            )
            deal_task_mapping[lead_task] = deal_task

            for lead_task, deal_task in deal_task_mapping.items():
                if lead_task.parent_task:
                    deal_task.parent_task = deal_task_mapping.get(lead_task.parent_task)
                    deal_task.save()

        # Eliminar el Lead original
        lead.delete()     

        # Agregar un mensaje para confirmar la conversión
        messages.success(request, "Lead converted to Deal successfully.")

    # Redireccionar a la página adecuada después de la conversión
    url = reverse('deal:list', kwargs={
            'organization_slug': organization_slug})
    return redirect(url)

class HomeLeadView(LoginRequiredMixin, TemplateView):
    template_name = 'operation/lead/lead_list.html'

    def get_context_data(self, **kwargs):        
        context = super().get_context_data(**kwargs)
        context['title'] = 'Leads'
        return context

# Query de Leads de la base de datos enviada a JS como JSON para las Datatables JS
class LeadListView(ListView, AgentRequiredMixin, AgentContextMixin):
    model = Lead

    def get_queryset(self):
        leads = Lead.objects.filter(organization=self.get_organization())
        return leads

    def get(self, request, *args, **kwargs):
        leads = self.get_queryset()
        leads_data = list(leads.values('id', 'lead_name', 'lead_source', 'first_name', 'last_name', 'primary_email', 'phone', 'mobile_phone', 'country', 'company_name',
                                       'created_time', 'last_modified_by_id', 'modified_time', 'assigned_to_id', 'organization__name', 'stage', 'organization__slug'))
        country_names = {
            country.id: country.name for country in Country.objects.all()
        }
        user_names = {
            user.id: f"{user.first_name} {user.last_name}" for user in User.objects.all()
        }

        # Diccionario para convertir valores de lead_source y stage a su representación legible
        lead_source_choices = dict(Lead.LEAD_SOURCE_CHOICES)
        stage_choices = dict(Deal.STAGE_CHOICES)

        for lead in leads_data:
            lead['country'] = country_names.get(lead['country'])
            lead['assigned_to'] = user_names.get(lead['assigned_to_id'])
            lead['last_modified_by'] = user_names.get(lead['last_modified_by_id'])
            # Convertir lead_source y stage de código a representación legible
            lead['lead_source'] = lead_source_choices.get(lead['lead_source'], 'Unknown') # Ver más detalles en la nota de Obsidian: [[Notas en el Codigo]]
            lead['stage'] = stage_choices.get(lead['stage'], 'Unknown') # Ver más detalles en la nota de Obsidian: [[Notas en el Codigo]]
            # Aquí agregas las URLs de actualización y Eliminacion
            lead['update_url'] = reverse('lead:update', kwargs={'pk': lead['id'], 'organization_slug': lead['organization__slug']})
            lead['delete_url'] = reverse('lead:delete', kwargs={'pk': lead['id'], 'organization_slug': lead['organization__slug']})

            # Obtener LeadProducts relacionados
            for lead in leads_data:
                lead_products = LeadProduct.objects.filter(lead_id=lead['id']).annotate(
                    product_url=F('product__product_url')
                ).values('id', 'product__name', 'product_url')
                
                lead['lead_products'] = list(lead_products)

            # Obtener DealTasks relacionadas
            lead_tasks = LeadTask.objects.filter(lead_id=lead['id']).values('id', 'name', 'stage', 'is_closed',
                                                                            'modified_time', 'assigned_to__id',
                                                                            'last_modified_by__id')
            # Para cada tarea, reemplazar user IDs con nombres reales usando el diccionario user_names
            lead_tasks = list(lead_tasks)
            for task in lead_tasks:
                task['assigned_to'] = user_names.get(task['assigned_to__id'])
                task['last_modified_by'] = user_names.get(task['last_modified_by__id'])
                # Asegúrate de eliminar las claves que ya no necesitas para evitar confusión
                del task['assigned_to__id']
                del task['last_modified_by__id']

            lead['lead_tasks'] = lead_tasks

        return JsonResponse({'leads': leads_data})


class LeadDetailView(DetailView, AgentRequiredMixin, AgentContextMixin):
    model = Lead
    template_name = 'operation/lead/lead_detail.html'
    context_object_name = 'lead'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lead = self.get_object()
        context['title'] = f'{ lead.lead_name}' 
        context['crud'] = "Detail Lead"
        # Añadir productos asociados al Lead
        lead_products = LeadProduct.objects.filter(lead=self.object)
        context['lead_products'] = lead_products
         # Obtener tareas asociadas al Lead
        lead_tasks = LeadTask.objects.filter(lead=self.object)
        context['lead_tasks'] = lead_tasks


        return context

class LeadCreateView(LoginRequiredMixin, FormView, AgentRequiredMixin, AgentContextMixin):
    template_name = 'operation/lead/lead_create.html'
    form_class = LeadForm

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        agent = self.request.user.agent

        if agent:
            form.fields['country'].queryset = Country.objects.filter(
                Q(organization=agent.organization) & Q(is_selected=True)
            )
            form.fields['assigned_to'].queryset = User.objects.filter(
                agent__organization=agent.organization)

            return form

    def form_valid(self, form):    
        agent = self.request.user.agent
        current_time = timezone.now()
        validation_error_handled = False

        try:
            lead = form.save(commit=False)
            # end_date_time no puede ser menor a start_date_time
            if lead.end_date_time and lead.start_date_time and lead.end_date_time < lead.start_date_time:
                raise ValidationError(
                    "La fecha de finalización no puede ser anterior a la fecha de inicio.")
            
            # Crea o Actualiza Company, Leads, Deals, Contact, Client, si el nuevo Lead tiene un company_email o primary_email existente          
            with transaction.atomic():
                new_email = form.cleaned_data.get('primary_email')
                lead_name = form.cleaned_data.get('lead_name')
                lead_source = form.cleaned_data.get('lead_source')
                first_name = form.cleaned_data.get('first_name')
                last_name = form.cleaned_data.get('last_name')
                title = form.cleaned_data.get('title')
                phone = form.cleaned_data.get('phone')
                mobile_phone = form.cleaned_data.get('mobile_phone')
                company_name = form.cleaned_data.get('company_name')
                new_company_email = form.cleaned_data.get('company_email')
                company_phone = form.cleaned_data.get('company_phone')
                website = form.cleaned_data.get('website')
                industry = form.cleaned_data.get('industry')
                country = form.cleaned_data.get('country')
                currency = form.cleaned_data.get('currency')
                description = form.cleaned_data.get('description')
                assigned_to = form.cleaned_data.get('assigned_to')
                last_modified_by = agent.user
                start_date_time = form.cleaned_data.get('start_date_time')
                end_date_time = form.cleaned_data.get('end_date_time')   
             
                # Verificar si ya existe una Company con el mismo company_email, si no, crearla
                company, company_created = Company.objects.get_or_create(
                    company_email=new_company_email,
                    defaults={
                        'company_name': company_name, 
                        'company_phone': company_phone, 
                        'website': website, 
                        'industry': industry, 
                        'created_by': agent.user,
                        'last_modified_by': agent.user,
                        'created_time' : current_time,
                        'modified_time' : current_time,
                        'organization': agent.organization,
                    }
                )

                if not company_created:
                    # Si la company ya existe, actualizarla
                    company.company_name = company_name
                    company.company_phone = company_phone
                    company.website = website
                    company.industry = industry
                    company.last_modified_by = agent.user
                    company.modified_time = current_time
                    company.save()
                    
                    # Actualiza todas los leads si Company existe
                    related_leads = Lead.objects.filter(company__company_email=new_company_email).exclude(pk=lead.pk)
                    for related_lead in related_leads:
                        # related_lead.company = company
                        related_lead.company_name = company_name
                        related_lead.company_phone = company_phone
                        related_lead.website = website
                        related_lead.industry = industry
                        related_lead.modified_time = current_time
                        related_lead.last_modified_by = agent.user
                        related_lead.save()

                # Buscar el Contact existente solo por primary_email
                contact = Contact.objects.filter(primary_email=new_email).first()

                if contact:
                    # Si el Contact existe
                    if company_created:
                        # Si la Company es nueva, crea un nuevo Contact con la misma primary_email
                        new_contact = Contact.objects.create(
                            primary_email=new_email,
                            first_name = first_name,
                            last_name = last_name,
                            title = title,
                            phone = phone,
                            mobile_phone = mobile_phone,
                            country = country,
                            created_by = agent.user,
                            last_modified_by = agent.user,
                            modified_time = current_time,
                            organization = agent.organization,
                            company=company,  # Asociar con la nueva Company
                        )
                    else:
                        # Si la Company ya existía, actualiza el Contact (sin cambiar la Company)
                        contact.first_name = first_name
                        contact.last_name = last_name
                        contact.title = title
                        contact.phone = phone
                        contact.mobile_phone = mobile_phone
                        contact.country = country
                        contact.last_modified_by = agent.user
                        contact.modified_time = current_time
                        contact.save()

                    # Actualizar todos los Contact que tengan el mismo primary_email
                    existing_contacts = Contact.objects.filter(primary_email=new_email)
                    for existing_contact in existing_contacts:
                        existing_contact.first_name = first_name
                        existing_contact.last_name = last_name
                        existing_contact.title = title
                        existing_contact.phone = phone
                        existing_contact.mobile_phone = mobile_phone
                        existing_contact.country = country
                        existing_contact.last_modified_by = agent.user
                        existing_contact.modified_time = current_time
                        existing_contact.save()                     

                else:
                    # Si el Contact no existe, crear uno nuevo asociado con la Company
                    contact = Contact.objects.create(
                        primary_email=new_email,
                        first_name = first_name,
                        last_name = last_name,
                        title = title,
                        phone = phone,
                        mobile_phone = mobile_phone,
                        country = country,
                        created_by = agent.user,
                        last_modified_by = agent.user,
                        modified_time = current_time,
                        organization = agent.organization,
                        company=company,  # Asociar con la nueva o existente Company
                    )  

                # Actualizar el Client asociado, si existe
                try:
                    client = Client.objects.get(primary_email=new_email)
                    client.primary_email = new_email
                    client.first_name = first_name
                    client.last_name = last_name
                    client.title = title
                    client.phone = phone
                    client.mobile_phone = mobile_phone
                    client.company = company
                    client.country = country
                    client.last_modified_by = agent.user
                    client.modified_time = current_time
                    client.save()                       

                except Client.DoesNotExist:
                    # No hay un Client con este primary_email, no se hace nada
                    pass

                # Crear el nuevo Lead
                lead = Lead.objects.create(
                    contact=contact,
                    company=company,
                    lead_name=lead_name,
                    lead_source=lead_source,
                    primary_email=new_email,
                    first_name=first_name,
                    last_name=last_name,
                    title = title,
                    phone = phone,
                    mobile_phone = mobile_phone,
                    company_name = company_name,
                    company_email = new_company_email,
                    company_phone = company_phone,
                    website = website,
                    industry = industry,
                    country = country,
                    currency = currency,
                    description = description,
                    created_by = agent.user,
                    assigned_to = assigned_to,
                    last_modified_by = agent.user,
                    start_date_time = start_date_time,
                    end_date_time = end_date_time,
                    organization = agent.organization,
                )
                lead.save()   
             
                # Actualizar todos los Leads asociados con este primary_email, sin los campos Company porque eso se hace arriba
                related_leads = Lead.objects.filter(primary_email=new_email).exclude(pk=lead.pk)
                for lead in related_leads:
                    lead_fields_to_update = []
                    for field, value in [
                        # ('contact', contact),
                        ('primary_email', new_email),
                        ('first_name', first_name),
                        ('last_name', last_name),
                        ('title', title),
                        ('phone', phone),
                        ('mobile_phone', mobile_phone),                       
                        ('country', country),
                        ('currency', currency),                        
                        ('last_modified_by', last_modified_by),
                    ]:
                        if getattr(lead, field) != value:
                            setattr(lead, field, value)
                            lead_fields_to_update.append(field)

                    if lead_fields_to_update:
                        lead.save(update_fields=lead_fields_to_update)                

                # Actualizar todos los Deals asociados con este primary_email
                related_deals = Deal.objects.filter(primary_email=new_email)
                for deal in related_deals:
                    deal_fields_to_update = []
                    for field, value in [
                        ('primary_email', new_email),
                        ('first_name', first_name),
                        ('last_name', last_name),
                        ('title', title),
                        ('phone', phone),
                        ('mobile_phone', mobile_phone),
                        ('currency', currency),
                        ('last_modified_by', last_modified_by),
                    ]:
                        if getattr(deal, field) != value:
                            setattr(deal, field, value)
                            deal_fields_to_update.append(field)

                    if deal_fields_to_update:
                        deal.save(update_fields=deal_fields_to_update)                
                
            messages.success(self.request, "Lead Creado correctamente")
            url = reverse('lead:list', kwargs={
                'organization_slug': agent.organization.slug})
            return redirect(url)

        except ValidationError as e:
            self.validation_error_handled = True  # Indica que se manejó un error
            # Agrega el error de ValidationError al sistema de mensajes
            error_message = '; '.join(e.messages) if hasattr(
                e, 'messages') else str(e)
            messages.error(self.request, error_message)
            # Agrega los errores del ValidationError al formulario y vuelve a mostrar el formulario
            form.add_error(None, e)
            # return self.form_invalid(form)
            # return render(self.request, self.template_name, {'form': form, 'organization_slug': agent.organization.slug})
            return render(self.request, self.template_name, {'form': form})

    def form_invalid(self, form):
        # print(form.errors)      
        current_lead_id = self.kwargs.get('pk')  # ID de la tarea actual
        task = get_object_or_404(LeadTask, pk=current_lead_id)
        lead = task.lead
        context = self.get_context_data()
        # Actualizar el contexto con datos específicos del formulario inválido
        context.update({
            'form': form,  # Asegurarse de pasar el formulario inválido
            'lead_pk': lead.id,  # ID del lead
            # 'organization_name': self.get_organization(),
        })
        if not self.validation_error_handled:
            messages.error(
                self.request, "Invalid form data. Please check the entries and try again.")
        return render(self.request, self.template_name,  context)    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] =  "Create Lead"
        
       
        # context['organization_name'] = self.get_organization()
        # if self.request.POST:
        #     context['formset'] = LeadProductFormset(self.request.POST)
        # else:
        #     context['formset'] = LeadProductFormset()

        return context

class LeadUpdateView(UpdateView, AgentRequiredMixin, AgentContextMixin):
    model = Lead
    template_name = 'operation/lead/lead_update.html'
    form_class = LeadUpdateForm
    validation_error_handled = False    

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        agent = self.request.user.agent
        current_time = timezone.now()
        # Obtener la instancia del lead
        lead = self.get_object()

        if agent:
            # Configuración de queryset para los campos que dependen del agente
            form.fields['country'].queryset = Country.objects.filter(
                Q(organization=agent.organization) & Q(is_selected=True)
            )
            form.fields['assigned_to'].queryset = User.objects.filter(
                agent__organization=agent.organization)          
                
        # Determinar el estado de los campos basado en las fechas de lead
        if lead.is_closed:
            # Deshabilitar todos los campos si el lead está cerrado
            for field in form.fields:
                form.fields[field].disabled = True
        else:
            # Estado predeterminado: habilitar todos los campos
            for field in form.fields:
                form.fields[field].disabled = False

            # Si end_date_time es pasado, deshabilita todos excepto 'extended_end_date_time'
            if lead.end_date_time and lead.end_date_time < current_time:
                for field in form.fields:
                    if field != 'extended_end_date_time':
                        form.fields[field].disabled = True              

            # Si extended_end_date_time es futuro, habilita todos excepto 'end_date_time'
            if lead.extended_end_date_time and lead.extended_end_date_time > current_time:
                for field in form.fields:
                    if field != 'end_date_time':
                        form.fields[field].disabled = False            


        return form            

    def form_valid(self, form):
        agent = self.request.user.agent
        form.instance.organization = agent.organization
        form.instance.last_modified_by = agent.user
        current_time = timezone.now()

        try:
            lead = form.save(commit=False)           
            # end_date_time no puede ser menor a start_date_time
            if lead.end_date_time and lead.start_date_time and lead.end_date_time < lead.start_date_time:
                raise ValidationError(
                    "La fecha de finalización no puede ser anterior a la fecha de inicio.")

            # end_date_time no puede ser mayor a extended_end_date_time
            if lead.extended_end_date_time and lead.end_date_time and lead.end_date_time > lead.extended_end_date_time:
                raise ValidationError(
                    "La fecha de finalización extendida no puede ser anterior a la fecha de finalización original.")

             # Logica para establecer el stage is_closed"
            if lead.stage == 'close_lost':
                lead.is_closed = True 

            # Guardar los formularios de LeadProduct
            formset = LeadProductFormset(
                self.request.POST, self.request.FILES, instance=lead)

            if formset.is_valid():
                formset.save()

            with transaction.atomic():
                # Captura el antiguo Contact y la antigua Company asociada al Lead, antes de cualquier cambio
                old_company = lead.company
                old_contact = lead.contact

                new_email = form.cleaned_data.get('primary_email')
                # Verificar si existe un Contact con el nuevo primary_email
                existing_contact = Contact.objects.filter(primary_email=new_email).first()

                lead_name = form.cleaned_data.get('lead_name')
                lead_source = form.cleaned_data.get('lead_source')
                first_name = form.cleaned_data.get('first_name')
                last_name = form.cleaned_data.get('last_name')
                title = form.cleaned_data.get('title')
                phone = form.cleaned_data.get('phone')
                mobile_phone = form.cleaned_data.get('mobile_phone')
                company_name = form.cleaned_data.get('company_name')
                new_company_email = form.cleaned_data.get('company_email')
                # Verificar si existe una Company con el nuevo company_email
                existing_company = Company.objects.filter(company_email=new_company_email).first()
                company_phone = form.cleaned_data.get('company_phone')
                website = form.cleaned_data.get('website')
                industry = form.cleaned_data.get('industry')

                country = form.cleaned_data.get('country')
                currency = form.cleaned_data.get('currency')

                description = form.cleaned_data.get('description')
                
                assigned_to = form.cleaned_data.get('assigned_to')
                last_modified_by = agent.user
                modified_time = current_time
                start_date_time = form.cleaned_data.get('start_date_time')
                end_date_time = form.cleaned_data.get('end_date_time')
                extended_end_date_time = form.cleaned_data.get('extended_end_date_time')

                stage = form.cleaned_data.get('stage')

                # Actualizar campos en el Lead
                lead_fields_to_update = [
                    'lead_name',
                    'lead_source',
                    'primary_email', 
                    'first_name',
                    'last_name',
                    'title',
                    'phone',
                    'mobile_phone', 
                    'company_name',
                    'company_email',
                    'company_phone', 
                    'website', 
                    'industry',          
                    'country', 
                    'currency', 
                    'description', 
                    'assigned_to', 
                    'last_modified_by',    
                    'modified_time',                                
                    'start_date_time', 
                    'end_date_time',
                    'extended_end_date_time',
                    'stage'
                ]

                # Si existe Company, relacionamos Company con el Lead, sino creamos Company y lo relacionamos con el Lead
                if existing_company:
                    # Si la Company existe, asignar esta Company al Lead actual
                    lead.company = existing_company                  
                else:
                    # Si no existe, crear una nueva Company
                    new_company=Company.objects.create(
                        company_email=new_company_email,
                        company_name=company_name,
                        company_phone=company_phone,
                        website=website,
                        industry=industry,
                        created_by=agent.user,
                        last_modified_by=last_modified_by,
                        created_time=current_time,                        
                        modified_time=current_time,
                        organization=agent.organization,
                    )
                    lead.company = new_company
                
                # Incluir 'company' en la lista de campos a actualizar
                if 'company' not in lead_fields_to_update:
                    lead_fields_to_update.append('company')

                if existing_contact:
                    # Si Contact existe, asignar este Contact al Lead actual
                    lead.contact = existing_contact
                else:
                    # Si no existe, crear un nuevo Contact
                    new_contact=Contact.objects.create(
                        primary_email=new_email,
                        first_name=first_name,
                        last_name=last_name,
                        title=title,
                        phone=phone,
                        mobile_phone=mobile_phone,
                        country=country,                       
                        created_by=agent.user,
                        last_modified_by=last_modified_by,
                        created_time=current_time,                        
                        modified_time=current_time,
                        organization=agent.organization,
                    )
                    # Asociar la nueva o existente Company con el nuevo Contact
                    new_contact.company = lead.company
                    new_contact.save(update_fields=['company'])

                    lead.contact = new_contact
                
                # Incluir 'contact' en la lista de campos a actualizar del lead
                if 'contact' not in lead_fields_to_update:
                    lead_fields_to_update.append('contact')

                # Guardamos el lead con todos los campos a actualizar
                lead.save(update_fields=lead_fields_to_update)              

                # Actualizar Companies y Leads relacionados (company_email)
                if existing_company:
                    # Actualizamos los campos de la Company si company_email existe
                    related_companies = Company.objects.filter(company_email=old_company.company_email)
                    for company in related_companies:
                        company_fields_to_update = []
                        for field, value in [
                            ('company_email', new_company_email),
                            ('company_name', company_name),
                            ('company_phone', company_phone),
                            ('website', website),
                            ('industry', industry),
                            ('last_modified_by', last_modified_by),
                            ('modified_time', current_time),
                        ]:
                            if getattr(company, field) != value:
                                setattr(company, field, value)
                                company_fields_to_update.append(field)

                        if company_fields_to_update:
                            company.save(update_fields=company_fields_to_update)   

                            # Actualizar otros Leads relacionados con Company si company_email existe
                            related_company_leads = Lead.objects.filter(company_email=old_company.company_email)
                            for lead in related_company_leads:
                                lead.company = lead.company
                                lead_fields_to_update = ['company'] # Inicializamos en 'company'                                
                                for field, value in [                       
                                    ('company_email', new_company_email),
                                    ('company_name', company_name),
                                    ('company_phone', company_phone),
                                    ('website', website),
                                    ('industry', industry),                     
                                ]:
                                    if getattr(lead, field) != value:
                                        setattr(lead, field, value)
                                        if field not in lead_fields_to_update:
                                            lead_fields_to_update.append(field)

                                if lead_fields_to_update:
                                    # Actualizar el company_id del Contact asociado con este Lead específico
                                    contact = lead.contact 
                                    if contact:
                                        contact.company = lead.company
                                        contact.save(update_fields=['company'])     

                                    lead.save(update_fields=lead_fields_to_update)

                            # Actualizar otros Deals relacionados con Company si company_email existe
                            related_company_deals = Deal.objects.filter(company_email=old_company.company_email) 
                            for deal in related_company_deals:
                                deal.company = lead.company
                                deal_fields_to_update = ['company'] # Inicializamos con 'company'
                                for field, value in [                       
                                    ('company_email', new_company_email),
                                    ('company_name', company_name),
                                    ('company_phone', company_phone),
                                    ('website', website),
                                    ('industry', industry),                     
                                ]:
                                    if getattr(deal, field) != value:
                                        setattr(deal, field, value)
                                        if field not in deal_fields_to_update:
                                            deal_fields_to_update.append(field)

                                if deal_fields_to_update:
                                    # Actualizar el company_id del Client asociado con este Deal específico
                                    client = deal.client 
                                    if client:
                                        client.company = deal.company
                                        client.save(update_fields=['company'])     

                                    deal.save(update_fields=deal_fields_to_update)          

                # Actualiza los otros Leads relacionados con la nueva Company si no existing_company
                else: 
                    # Encuentra todos los Leads que tenían el antiguo company_email
                    old_company_email_leads = Lead.objects.filter(company_email=old_company.company_email)   

                    for lead in old_company_email_leads:
                        lead.company = new_company
                        for field, value in [
                            ('company_name', company_name),
                            ('company_email', new_company_email),
                            ('company_phone', company_phone),
                            ('website', website),
                            ('industry', industry),
                        ]:
                            if getattr(lead, field) != value:
                                setattr(lead, field, value)
                                if field not in lead_fields_to_update:
                                    lead_fields_to_update.append(field)                      

                            lead.save(update_fields=lead_fields_to_update)

                    # Actualizar el company_id del Contact asociado con este Lead específico
                    contact = lead.contact 
                    if contact:
                        contact.company = lead.company
                        contact.save(update_fields=['company'])     

                    # Actualizar Deals relacionados con la nueva Company
                    old_company_email_deals = Deal.objects.filter(company_email=old_company.company_email)
                    for deal in old_company_email_deals:
                        deal.company = new_company
                        deal_fields_to_update = ['company'] # Inicializamos con 'company'
                        for field, value in [
                            ('company_name', company_name),
                            ('company_email', new_company_email),
                            ('company_phone', company_phone),
                            ('website', website),
                            ('industry', industry),
                        ]:
                            if getattr(deal, field) != value:
                                setattr(deal, field, value)
                                if field not in deal_fields_to_update:
                                    deal_fields_to_update.append(field)
                        
                        if deal_fields_to_update:
                            # Actualizar el company_id del Client asociado con este Deal específico
                            client = deal.client 
                            if client:
                                client.company = deal.company
                                client.save(update_fields=['company'])     

                            deal.save(update_fields=deal_fields_to_update)          
               
               # EXISTING OR NOT CLIENTS AND CONTACTS (primary_email)
                                                        
                # Actualizar Contacts, Clients, Deals y Leads relacionados (primary_email)
                if existing_contact:
                    # Actualizar Contacts relacionados (primary_email)
                    related_contacts = Contact.objects.filter(primary_email=old_contact.primary_email).exclude(pk=lead.pk)
                    for contact in related_contacts:
                        contact_fields_to_update = []
                        for field, value in [
                            ('primary_email', new_email), 
                            ('first_name', first_name), 
                            ('last_name', last_name), 
                            ('title', title), 
                            ('phone', phone), 
                            ('mobile_phone', mobile_phone), 
                            ('country', country),
                            ('last_modified_by', last_modified_by),
                            ('modified_time', current_time),
                        ]:                
                            if getattr(contact, field) != value:
                                setattr(contact, field, value)
                                contact_fields_to_update.append(field)                  

                        if contact_fields_to_update:
                            contact.save(update_fields=contact_fields_to_update)          

                            # Buscar y actualizar los Client correspondientes
                            try:
                                related_clients = Client.objects.filter(primary_email=old_contact.primary_email).exclude(pk=lead.pk)
                                for client in related_clients:                                               
                                    for field in contact_fields_to_update:
                                        if field != 'company':
                                            setattr(client, field, getattr(contact, field))
                                    if existing_company:
                                        # Si la Company existe, asignar esta Company al Client actual
                                        client.company = existing_company
                                        # Incluir 'company' en la lista de campos a actualizar
                                        if 'company' not in contact_fields_to_update:
                                            contact_fields_to_update.append('company')
                                    # setattr(client, field, getattr(contact, field))
                                    client.save()

                                    # Actualizar todos los Deals relacionados con este Client
                                    related_deals = client.client_deals.all()
                                    for deal in related_deals:
                                        for field in contact_fields_to_update:
                                            setattr(deal, field, getattr(client, field))
                                        deal.save()

                            except Client.DoesNotExist:
                                # No hay un Client con este primary_email, no se necesita hacer nada más
                                pass        

                    # Actualizar otros Leads relacionados (primary_email)
                    related_leads = Lead.objects.filter(primary_email=old_contact.primary_email)
                    for lead in related_leads:
                        lead.company = lead.company
                        lead_fields_to_update = ['company'] #  Inicializamos en 'company'
                        for field, value in [
                            ('primary_email', new_email),
                            ('first_name', first_name),
                            ('last_name', last_name),
                            ('title', title),
                            ('phone', phone),
                            ('mobile_phone', mobile_phone),                      
                            ('country', country),
                            ('currency', currency),
                            ('last_modified_by', last_modified_by),
                            ('modified_time', current_time),
                        ]:
                            if getattr(lead, field) != value:
                                setattr(lead, field, value)
                                lead_fields_to_update.append(field)

                        if lead_fields_to_update:
                            lead.save(update_fields=lead_fields_to_update)

                # Actualiza los otros Leads relacionados con el nuevo Contact
                else: 
                    old_primary_email_leads = Lead.objects.filter(primary_email=old_contact.primary_email)
                    for lead in old_primary_email_leads:
                        # Actualizar el company_id del Contact asociado con este Lead específico  
                        lead.contact = new_contact
                        # Lista de campos a actualizar
                        lead_fields_to_update = ['contact']  # Inicializar con 'contact'
                        for field, value in [
                            ('primary_email', new_email),
                            ('first_name', first_name),
                            ('last_name', last_name),
                            ('title', title),
                            ('phone', phone),
                            ('mobile_phone', mobile_phone),                      
                            ('country', country),
                            ('currency', currency),
                            ('last_modified_by', last_modified_by),
                            ('modified_time', current_time),
                        ]:
                            if getattr(lead, field) != value:
                                setattr(lead, field, value)
                                lead_fields_to_update.append(field)

                        if lead_fields_to_update:
                            lead.save(update_fields=lead_fields_to_update)

                    # Comprobar si el nuevo email ya existe en Client o Deal
                    email_exists_in_client = Client.objects.filter(primary_email=new_email).exists()
                    email_exists_in_deal = Deal.objects.filter(primary_email=new_email).exists()
                    
                    if email_exists_in_client or email_exists_in_deal:
                        # Buscar y actualizar los Contact correspondientes
                        try:
                            related_clients = Client.objects.filter(primary_email=new_email)
                            for client in related_clients:
                                client_fields_to_update = []    
                                for field, value in [
                                    ('primary_email', new_email), 
                                    ('first_name', first_name), 
                                    ('last_name', last_name), 
                                    ('title', title), 
                                    ('phone', phone), 
                                    ('mobile_phone', mobile_phone), 
                                    ('country', country),
                                    ('last_modified_by', last_modified_by),
                                    ('modified_time', current_time),
                                ]:                
                                    if getattr(client, field) != value:
                                        setattr(client, field, value)
                                        client_fields_to_update.append(field)                  

                                if client_fields_to_update:
                                    client.save(update_fields=client_fields_to_update)                          

                                # Actualizar todos los Deals relacionados con este Client
                                related_deals = client.client_deals.all()
                                for deal in related_deals:
                                    for field in client_fields_to_update:
                                        setattr(deal, field, getattr(client, field))
                                    deal.save()

                        except Client.DoesNotExist:
                            # No hay un Client con este primary_email, no se necesita hacer nada más
                            pass    
                        
                    else: 
                        try:
                            # Filtrar Clients que tienen el nuevo email o el email antiguo del Contact
                            related_clients = Client.objects.filter(Q(primary_email=new_email) | Q(primary_email=old_contact.primary_email))
                            for client in related_clients:
                                client_fields_to_update = []    
                                for field, value in [
                                    ('primary_email', new_email), 
                                    ('first_name', first_name), 
                                    ('last_name', last_name), 
                                    ('title', title), 
                                    ('phone', phone), 
                                    ('mobile_phone', mobile_phone), 
                                    ('country', country),
                                    ('last_modified_by', last_modified_by),
                                    ('modified_time', current_time),
                                ]:                
                                    if getattr(client, field) != value:
                                        setattr(client, field, value)
                                        client_fields_to_update.append(field)                  

                                if client_fields_to_update:
                                    client.save(update_fields=client_fields_to_update)                          

                                # Actualizar todos los Deals relacionados con este Client
                                related_deals = client.client_deals.all()
                                for deal in related_deals:
                                    for field in client_fields_to_update:
                                        setattr(deal, field, getattr(client, field))
                                    deal.save()

                        except Client.DoesNotExist:
                            # No hay un Client con este primary_email, no se necesita hacer nada más
                            pass   

                # ELIMINA Company Y Client QUE NO TENGAN DEALS RELACIONADOS

                # Buscar todas las Company que no tienen Leads ni Deals relacionados
                companies_to_check = Company.objects.annotate(
                    num_leads=Count('company_leads'),
                    num_deals=Count('company_deals')
                )
                # Filtra las Company que no tienen ni Leads ni Deals
                companies_without_leads_and_deals = companies_to_check.filter(num_leads=0, num_deals=0)
                # Elimina las Company que cumplen con la condición
                companies_without_leads_and_deals.delete()

                # Buscar todos los Contact que no tienen Leads asociados
                contacts_without_leads = Contact.objects.annotate(num_leads=Count('contact_leads')).filter(num_leads=0)
                # Eliminar estos Contact
                contacts_without_leads.delete()

            messages.success(self.request, "Lead actualizado")
            url = reverse('lead:update', kwargs={
                'organization_slug': self.get_organization().slug, 'pk': self.object.pk})
            return redirect(url)
        
        except ValidationError as e:
            self.validation_error_handled = True  # Indica que se manejó un error
            # Agrega el error de ValidationError al sistema de mensajes
            error_message = '; '.join(e.messages) if hasattr(
                e, 'messages') else str(e)
            messages.error(self.request, error_message)
            # Agrega los errores del ValidationError al formulario y vuelve a mostrar el formulario
            form.add_error(None, e)
            return self.form_invalid(form)
        

    def form_invalid(self, form):  
        # print(form.errors)
        lead = self.get_object()
        context = self.get_context_data()
            # Actualizar el contexto con datos específicos del formulario inválido
        context.update({
            'form': form,  # Asegurarse de pasar el formulario inválido
            'lead_pk': lead.id,  # ID del lead
            # 'organization_name': self.get_organization(),
        })
        if not self.validation_error_handled:
            messages.error(
                self.request, "Invalid form data. Please check the entries and try again.")
        return render(self.request, self.template_name,  context)    

      
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lead = self.get_object()
        organization = self.get_organization()
        context['pk'] = lead.pk
        context['title'] = f"{lead.lead_name}"
        context['crud'] = "Update Lead"

        # context['organization_name'] = self.get_organization()
        current_time = timezone.now()

        # Determina si deshabilitan los botones update y create task
        context['enable_update'] = True
        context['enable_button'] = True
        if lead.end_date_time and lead.end_date_time < current_time and not lead.extended_end_date_time:
            context['enable_button'] = False            
        if lead.extended_end_date_time and lead.extended_end_date_time < current_time:
            context['enable_button'] = False
        if lead.stage == 'close_lost':
            context['enable_update'] = False
            context['enable_button'] = False  

        # Determina si debe ocultarse el campo extended_end_date_time
        context['hide_extended_end_date_time'] = False
        if lead.end_date_time and lead.end_date_time > current_time:
            context['hide_extended_end_date_time'] = True 
            
        if self.request.POST:
            context['formset'] = LeadProductFormset(
            self.request.POST, instance=lead,
            form_kwargs={'organization': organization})  # Pasar la organización al formulario
        else:
            context['formset'] = LeadProductFormset(
            instance=lead,
            form_kwargs={'organization': organization})  # Pasar la organización al formulario

        # VALIDACIONES PARA FORMSET        
        # Determinar el estado de los campos basado en las fehas de lead
        if lead.is_closed:
            # Deshabilitar todos los campos si el lead está cerrado
            for form in context['formset']:
                for field in form.fields:
                    form.fields[field].disabled = True
        else:
            # Estado predeterminado: habilitar todos los campos
            for form in context['formset']:
                for field in form.fields:
                    form.fields[field].disabled = False

            # Si end_date_time es pasado, deshabilita todos excepto 'extended_end_date_time'
            if lead.end_date_time and lead.end_date_time < current_time:
                for form in context['formset']:
                    for field in form.fields:
                        form.fields[field].disabled = True           

            # Si extended_end_date_time es futuro, habilita todos excepto 'end_date_time'
            if lead.extended_end_date_time and lead.extended_end_date_time > current_time:
                for form in context['formset']:
                    for field in form.fields:
                        form.fields[field].disabled = False       
                    

        return context

class LeadDeleteView(DeleteView, AgentRequiredMixin, AgentContextMixin):
    model = Lead
    template_name = 'operation/lead/lead_delete.html'
    context_object_name = 'lead'

    def form_valid(self, form):
        with transaction.atomic():
            self.object = self.get_object()
            contact = self.object.contact

            # Verificar si el Contact está asociado con otros Lead
            if contact and contact.contact_leads.count() <= 1:
                # Si solo está asociado con este Lead, eliminar el Contact
                contact.delete()

            # ELIMINA Company Y Client QUE NO TENGAN DEALS RELACIONADOS

            # Buscar todas las Company que no tienen Leads ni Deals relacionados
            companies_to_check = Company.objects.annotate(
                num_leads=Count('company_leads'),
                num_deals=Count('company_deals')
            )
            # Filtra las Company que no tienen ni Leads ni Deals
            companies_without_leads_and_deals = companies_to_check.filter(num_leads=0, num_deals=0)
            # Elimina las Company que cumplen con la condición
            companies_without_leads_and_deals.delete()

            # Buscar todos los Client que no tienen Deals asociados
            clients_without_deals = Client.objects.annotate(num_deals=Count('client_deals')).filter(num_deals=0)
            # Eliminar estos Client
            clients_without_deals.delete()

        response = super(LeadDeleteView, self).form_valid(form)
        messages.success(self.request, "Lead Deleted.")
        return response

    def get_success_url(self):  
        return reverse_lazy('lead:list', kwargs={'organization_slug': self.get_organization().slug})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lead = self.get_object()
        context['title'] = f'{ lead.lead_name}' 
        context['crud'] = "Delete Lead"
        # context['organization_name'] = self.get_organization()
        return context


# ************
  # CUR TASK
# ************


class LeadHomeTaskView(LoginRequiredMixin, TemplateView):
    template_name = 'operation/leadtask/task_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Lead Tasks'
        return context


# Query de Tasks de la base de datos enviada a JS como JSON para las Datatables JS
class LeadTaskListView(ListView, AgentRequiredMixin, AgentContextMixin):
    model = LeadTask

    def get_queryset(self):
        return LeadTask.objects.filter(
            organization=self.get_organization()
        ).select_related('assigned_to', 'last_modified_by')
    
    def get(self, request, *args, **kwargs):
        tasks = self.get_queryset()
        tasks_data = list(tasks.values('id', 'name', 'last_modified_by_id', 'assigned_to_id', 'organization', 'modified_time', 
                                'created_by_id', 'stage', 'lead__id', 'lead_product__product__name', 'lead__lead_name', 'organization__slug'))
        user_names = {
            user.id: f"{user.first_name} {user.last_name}" for user in User.objects.all()
        }

        # Diccionario para convertir valores de stage a su representación legible
        stage_choices = dict(LeadTask.STAGE_CHOICES)

        for task in tasks_data:
            task['created_by'] = user_names.get(task['created_by_id'])
            task['assigned_to'] = user_names.get(task['assigned_to_id'])
            task['last_modified_by'] = user_names.get(task['last_modified_by_id'])
            task['organization'] = self.get_organization().name
            task['product_name'] = task['lead_product__product__name']  # Asigna el nombre del producto a una nueva clave
            task['lead_name'] = task['lead__lead_name']  # Nombre del lead
            # Convertir stage de código a representación legible
            task['stage'] = stage_choices.get(task['stage'], 'Unknown') # Ver más detalles en la nota de Obsidian: [[Notas en el Codigo]]
             # Aquí agregas las URLs de actualización y Eliminacion
            task['update_url'] = reverse('lead:task-update', kwargs={'pk': task['id'], 'organization_slug': task['organization__slug']})
            task['delete_url'] = reverse('lead:task-delete', kwargs={'pk': task['id'], 'organization_slug': task['organization__slug']})

        return JsonResponse({'tasks': tasks_data})


class LeadTaskCreateView(FormView, AgentRequiredMixin, AgentContextMixin):
    model = LeadTask
    template_name = 'operation/leadtask/task_create.html'
    form_class = LeadTaskCreateForm
    validation_error_handled = False

    def get_form(self, form_class=None):
        form = super().get_form(form_class)       
        agent = self.request.user.agent
        lead_id = self.kwargs.get('lead_pk')
        lead = get_object_or_404(Lead, pk=lead_id)
       
        if agent:
            # Configuración de queryset para los campos que dependen del agente
            form.fields['assigned_to'].queryset = User.objects.filter(
                agent__organization=agent.organization)        
            
        if lead:
            # Filtra los productos del lead
            form.fields['lead_product'].queryset = LeadProduct.objects.filter(lead=lead)       

            # Preparando el queryset de tareas relacionadas al lead y excluyendo parent tasks y sub-tareas
            # Excluir las tareas que son subtask
            tasks_to_exclude = LeadTask.objects.filter(parent_task__isnull=False).values_list('id', flat=True)

            # Filtrar tareas elegibles para ser parent_task
            eligible_tasks = LeadTask.objects.filter(
                lead=lead
            ).exclude(
                id__in=tasks_to_exclude
            )

            # Si no hay tareas elegibles, ocultar el campo parent_task
            if not eligible_tasks.exists():
                del form.fields['parent_task']
            else:
                form.fields['parent_task'].queryset = eligible_tasks
          
            # Configurar el campo parent_task si se está creando una subtarea
            parent_task_id = self.request.GET.get('parent_task')
            if parent_task_id:
                try:
                    parent_task_id = int(parent_task_id)  # Asegúrate de que es un entero
                    form.fields['parent_task'].initial = parent_task_id
                    form.fields['parent_task'].disabled = True  # Hacer el campo no editable
                except ValueError:
                    # Manejar el caso en que parent_task_id no sea un entero
                    pass   

        return form

    def form_valid(self, form):
        try:
            # self.validation_error_handled = False
            agent = self.request.user.agent
            task = form.save(commit=False)
            task.organization = agent.organization
            task.created_by = agent.user
            task.last_modified_by = agent.user

            # Capturar el ID del Lead desde la URL
            lead_id = self.kwargs.get('lead_pk')
            # Obtener el objeto Lead
            lead = get_object_or_404(Lead, pk=lead_id)
            # Asegura que el Lead con este ID existe para evitar errores
            if lead:
                task.lead = get_object_or_404(Lead, pk=lead_id)

                 # Obtiene el ID de parent_task desde la URL (si existe)
                parent_task_id = form.cleaned_data.get('parent_task_id')             
                if parent_task_id:
                    try:
                        parent_task_id = int(parent_task_id)  # Convierte a entero
                        # Asigna el objeto parent_task al task actual
                        task.parent_task = LeadTask.objects.get(id=parent_task_id)
                        # task.parent_task = parent_task_id
                    except (ValueError, LeadTask.DoesNotExist):
                        # Manejar el caso en que parent_task_id no sea un entero o no exista
                        messages.error(self.request, "Parent Task inválido.")
                        return self.form_invalid(form)

                messages.success(self.request, "Task creada correctamente")
                # Guarda el objeto Task
                task.save()                   
                
            else:
                # Cuando no tenga un lead asociado
                messages.error(
                    self.request, "El Task no tiene un Lead asociado.")
                return self.form_invalid(form)

            # Redirige a una URL específica después de la creación, como la página update del lead asociado
            url = reverse('lead:task-list', kwargs={
                'organization_slug': agent.organization.slug})
            return redirect(url)

        except ValidationError as e:
            self.validation_error_handled = True  # Indica que se manejó un error
            # Agrega el error de ValidationError al sistema de mensajes
            error_message = '; '.join(e.messages) if hasattr(
                e, 'messages') else str(e)
            messages.error(self.request, error_message)
            # Agrega los errores del ValidationError al formulario y vuelve a mostrar el formulario
            form.add_error(None, e)

            return self.form_invalid(form)

    def form_invalid(self, form):
        # print(form.errors)
        current_task_id = self.kwargs.get('pk')  # ID de la tarea actual
        task = get_object_or_404(LeadTask, pk=current_task_id)
        lead = task.lead

        if not self.validation_error_handled:
            messages.error(
                self.request, "Invalid form data. Please check the entries and try again.")
        return render(self.request, self.template_name, {
            'form': form,
            # 'organization_name': self.get_organization(),
            'lead_pk': lead.id,
        })   


    def get_context_data(self, **kwargs):
        # Asegúrate de que el contexto contenga todos los datos necesarios para la plantilla
        context = super().get_context_data(**kwargs)        
        # Obtener el ID del Lead de los argumentos de la URL
        lead_id = self.kwargs.get('lead_pk')
        lead = get_object_or_404(Lead, pk=lead_id)  # Obtener el objeto Lead

        # Componer el título y añadirlo al contexto
        if lead.lead_name:
            context['title'] = f"{lead.lead_name }"
        else:
            context['title'] = "Task Create"
        context['lead'] = lead
        context['lead_name'] = lead.lead_name if lead else None
        context['lead_pk'] = lead_id
        context['crud'] = "Create Lead Task"

        return context
    

class LeadTaskDetailView(DetailView, AgentRequiredMixin, AgentContextMixin):
    model = LeadTask
    template_name = 'operation/leadtask/task_detail.html'
    context_object_name = 'task'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.get_object()
        context['title'] = f'{ task.name }' 
        context['crud'] = "Detail Lead Task"
       # Obtener el producto asociado a la tarea
        task = context['task']  # Esta es la instancia de Task que DetailView está mostrando
        task_product = None  # Inicializa como None por si no hay producto asociado        
        # Verifica si la tarea tiene un lead_product y, por lo tanto, un producto
        if task.lead_product:
            task_product = task.lead_product.product.name  # Sigue la relación hasta llegar al nombre del producto
        context['task_product'] = task_product  # Agrega el producto al contexto

         # Obtener todas las subtareas asociadas a esta tarea
        subtasks = task.parent_leadtask.all()  # Usa la relación inversa definida por 'related_name'
        # Agrega las subtareas al contexto
        context['subtasks'] = subtasks

        # Verifica si la tarea actual es una subtarea y tiene una tarea padre
        if task.parent_task:
            context['parent_task'] = task.parent_task
        else:
            context['parent_task'] = None  # O asignar un valor por defecto si no hay tarea padre

  
        return context
    

class LeadTaskDeleteView(DeleteView, AgentRequiredMixin, AgentContextMixin):
    model = LeadTask
    template_name = 'operation/leadtask/task_delete.html'
    context_object_name = 'task'

    def get_success_url(self):
        messages.success(self.request, "Task Deleted.")
        return reverse_lazy('lead:task-list', kwargs={'organization_slug': self.get_organization().slug})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.get_object()
        context['title'] = f'{ task.name }' 
        context['crud'] = "Delete Lead Task"
        context['lead_name'] = context['task'].lead.lead_name  # Add lead_name to context
        return context


class LeadTaskUpdateView(UpdateView, AgentRequiredMixin, AgentContextMixin):
    model = LeadTask
    template_name = 'operation/leadtask/task_update.html'
    form_class = LeadTaskUpdateForm
    validation_error_handled = False

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        agent = self.request.user.agent
        current_task_id = self.kwargs.get('pk')  # ID de la tarea actual
        task = get_object_or_404(LeadTask, pk=current_task_id)
        lead = task.lead  # Obteniendo el lead asociado a la tarea

        if agent:
            # Configuración de queryset para los campos que dependen del agente
            form.fields['assigned_to'].queryset = User.objects.filter(
                agent__organization=agent.organization)            
        
        if lead:
            # Filtra los productos del lead
            form.fields['lead_product'].queryset = LeadProduct.objects.filter(lead=lead)

            # Preparando el queryset de tareas relacionadas al lead y excluyendo la tarea actual, parent tasks y sub-tareas
            # Seleccionamos la tarea actual
            current_task_id = self.kwargs.get('pk')
            current_task = get_object_or_404(LeadTask, pk=current_task_id)

            # Excluir la tarea actual y las tareas que son subtask
            tasks_to_exclude = LeadTask.objects.filter(parent_task__isnull=False).values_list('id', flat=True)
            tasks_to_exclude = list(tasks_to_exclude) + [current_task_id]

            # Ajustar el queryset del campo parent_task
            form.fields['parent_task'].queryset = LeadTask.objects.filter(
                lead=current_task.lead
            ).exclude(
                id__in=tasks_to_exclude
            )         

            # Configurar el campo parent_task si se está creando una subtarea
            if 'parent_task_id' in self.kwargs:
                parent_task_id = self.kwargs['parent_task_id']
                # Establecer el valor por defecto de parent_task aquí
                form.fields['parent_task'].initial = parent_task_id   

            # Deshabilitar el formulario de la current task y subtasks, si la tarea está cerrada
            if current_task.is_closed:
                for field in form.fields.values():
                    field.disabled = True

           # Comprobar si la tarea tiene padres o hijos
           # Condición 1: Si una tarea es padre, no puede ser hija
            if LeadTask.objects.filter(parent_task=current_task).exists():
                form.fields['parent_task'].disabled = True

            # Condición 2 y 3: Si una tarea es hija, no puede ser padre ni cambiar de padre
            if current_task.parent_task:
                form.fields['parent_task'].disabled = True
                  
            return form
                

    def form_valid(self, form):
        try:
            # self.validation_error_handled = False
            agent = self.request.user.agent
            current_task_id = self.kwargs.get('pk')  # ID de la tarea actual
            task = get_object_or_404(LeadTask, pk=current_task_id)
            task.organization = agent.organization
            task.created_by = agent.user
            task.last_modified_by = agent.user
            lead = task.lead  # Obteniendo el lead asociado a la tarea
            current_time = timezone.now()
            
            # Asegura que el Lead con este ID existe para evitar errores
            if lead:
                task = form.save(commit=False)
                task.lead = get_object_or_404(Lead, pk=lead.id) 

                if lead.is_closed:
                    messages.error(self.request, "El Lead esta cerrado.")
                    return self.form_invalid(form)            
                
                # Validaciones basadas en el estado de la tarea
                if task.is_closed:
                    messages.error(self.request, "La tarea esta cerrada.")
                    return self.form_invalid(form)
                # Validaciones basadas en las fechas de cierre del Lead
                if lead.extended_end_date_time and lead.extended_end_date_time < current_time:
                    # Implementa la lógica adecuada si el lead ha pasado su fecha extendida de cierre
                    messages.error(self.request, "El Lead esta cerrado.")
                    return self.form_invalid(form) 
                elif lead.end_date_time and lead.end_date_time < current_time and not lead.extended_end_date_time:
                    messages.error(self.request, "El Lead esta cerrado.")
                    return self.form_invalid(form)    

                # Logica para establecer el stage is_closed"
                if task.stage in ['completed', 'canceled']:
                    task.is_closed = True
                    # También marcar como cerrada las subtareas si la tarea principal está cerrada
                    for subtask in task.parent_leadtask.all():
                        subtask.is_closed = True 
                        subtask.save()
             
                # Guarda el objeto Task                
                messages.success(self.request, "Task editada correctamente")
                task.save()

            else:
                # Cuando no tenga un lead asociado
                messages.error(
                    self.request, "El Task no tiene un Lead asociado.")
                return self.form_invalid(form)

            # Redirige a una URL específica después de editar la tarea, como la página update del lead asociado
            url = reverse('lead:task-update', kwargs={
                'organization_slug': agent.organization.slug, 'pk': current_task_id})
            return redirect(url)


        except ValidationError as e:
            self.validation_error_handled = True  # Indica que se manejó un error
            # Agrega el error de ValidationError al sistema de mensajes
            error_message = '; '.join(e.messages) if hasattr(e, 'messages') else str(e) 
            messages.error(self.request, error_message)
            # Agrega los errores del ValidationError al formulario y vuelve a mostrar el formulario
            form.add_error(None, e)

            return self.form_invalid(form)

    def form_invalid(self, form):
        # print(form.errors)
        current_task_id = self.kwargs.get('pk')  # ID de la tarea actual
        task = get_object_or_404(LeadTask, pk=current_task_id)
        lead = task.lead
        context = self.get_context_data()
        # Actualizar el contexto con datos específicos del formulario inválido
        context.update({
            'form': form,  # Asegurarse de pasar el formulario inválido
            'lead_pk': lead.id,  # ID del lead
            # 'organization_name': self.get_organization(),
        })
        if not self.validation_error_handled:
            messages.error(
                self.request, "Invalid form data. Please check the entries and try again.")
        return render(self.request, self.template_name,  context)    
    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)        
        # Si se está pasando un ID de tarea parent como parámetro para crear una subtarea
        context['parent_task_id'] = self.request.GET.get('parent_task')
        current_time = timezone.now()
        # Obtener el ID del Lead de los argumentos de la URL
        current_task_id = self.kwargs.get('pk')  # ID de la tarea actual
        task = get_object_or_404(LeadTask, pk=current_task_id)
        lead = task.lead  # Obteniendo el lead asociado a la tarea
        # Componer el título y añadirlo al contexto
        if lead.lead_name:
            context['title'] = f"{lead.lead_name }"
        else:
            context['title'] = "Task Update"
        context['task'] = task
        context['lead'] = lead
        context['lead_pk'] = lead.id
        context['pk'] = current_task_id
        context['lead_name'] = lead.lead_name if lead else None
        context['crud'] = "Update Lead Task"

        # Determina si deshabilia los botones del formulario
        context['enable_button'] = True

        # Verificar si la tarea actual no es una subtask (no tiene parent_task)
        if not task.parent_task:
            # Habilitar el botón si también se cumple la condición de la fecha del lead
            context['enable_button'] = True
        else:
            context['enable_button'] = False

        if lead.extended_end_date_time and lead.extended_end_date_time < current_time:
            context['enable_button'] = False

        if lead.end_date_time and not lead.extended_end_date_time and lead.end_date_time < current_time:
            context['enable_button'] = False

        # datos para validar habilitar o deshabilitar los campos del formulario con JS de acuerdo al estado del lead y la tarea
        context['is_lead_closed'] = lead.is_closed
        context['is_task_closed'] = task.is_closed
        context['extended_end_date_time'] = lead.extended_end_date_time
        context['end_date_time'] = lead.end_date_time


        return context