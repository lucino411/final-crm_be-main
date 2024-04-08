let dataTable;
let dataTableIsInitialized = false;
let dataOption;

const dataTableOptions = {
    columnDefs: [
        { className: 'centered', targets: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] },
        { orderable: false, targets: [0, 1, 2, 5, 8] },
        { searchable: false, targets: [0, 1] },
    ],
    pageLength: 5,
    destroy: true,
    // dom: 'Bfrtip',
    dom: 'QBfrtip',

    initComplete: function () {
        let api = this.api();

        api.columns([4, 8, 9]).every(function () {
            let column = this;

            let select = document.createElement('select');
            select.add(new Option(''));
            column.footer().replaceChildren(select);

            select.addEventListener('change', function () {
                var val = DataTable.util.escapeRegex(select.value);

                column
                    .search(val ? '^' + val + '$' : '', true, false)
                    .draw();
            });

            column
                .data()
                .unique()
                .sort()
                .each(function (d, j) {
                    select.add(new Option(d));
                });
        });

        // Hace un filtro al hacer clic sobre cualquier campo, menos en la columna 1
        api.on('click', 'tbody td', function (e) {
            let columnIndex = api.cell(this).index().column;

            // Si el índice de la columna es diferente de 1, realiza la búsqueda
            if (columnIndex !== 1) {
                api.search(this.innerHTML).draw();
            }
        });


    },


    // BOTONES DESCARGAR
    buttons: [
        {
            extend: 'collection',
            text: 'Exportar',
            buttons: [
                {
                    extend: 'csv',
                    text: '<u>C</u>SV',
                    key: {
                        key: 'c',
                        altKey: true
                    }
                },
                {
                    extend: 'print',
                    text: '<u>P</u>rint',
                    key: {
                        key: 'p',
                        altKey: true
                    }
                },
                {
                    extend: 'pdf',
                    text: '<u>P</u>DF',
                    key: {
                        key: 'p',
                        altKey: true
                    }
                },
            ]
        }
    ],
};

const initDataTable = async () => {
    if (dataTableIsInitialized) {
        dataTable.destroy();
    }

    await listLeads();

    dataTable = $("#datatable-leads").DataTable({
        ...dataTableOptions,
        select: true  // Agrega esta línea dentro de las opciones
    });

    dataTableIsInitialized = true;
};


const listLeads = async () => {
    try {
        const leadListElement = document.getElementById('lead-list');
        const organizationSlug = leadListElement.dataset.organizationSlug;
        const response = await fetch(`${BASE_URL}/${organizationSlug}/lead/leads_json`);
        console.log(response)
        const data = await response.json();
        let content = ``;

        data.leads.forEach((lead, index) => {
            const leadData = lead;

            // console.log(leadData); // Agrega esta línea para imprimir leadData en la consola

            const createdTime = new Date(leadData.created_time).toLocaleString('es', { day: 'numeric', month: 'short', year: 'numeric' });
            // const modifiedTime = new Date(leadData.modified_time).toLocaleString('es', { day: 'numeric', month: 'short', year: 'numeric' });

            content += `
        <tr>
            <td>${index + 1}</td>
            <td><a href="/${leadData.organization}/lead/${leadData.id}/" class='table-link'>${leadData.first_name}</a></td>
            <td>${leadData.last_name}</td>
            <td>${leadData.primary_email}</td>
            <td>${leadData.country}</td>
            <td>${createdTime}</td> 
            <td>${leadData.last_modified_by}</td> 
            <td>${leadData.assigned_to}</td>
            <td>${leadData.created_by}</td>
            <td>${leadData.organization}</td>      
        </tr>
        `;
        });
        tableBody_leads.innerHTML = content;
    } catch (e) {
        alert(e);
    }
};

window.addEventListener("load", async () => {
    await initDataTable();
});

// A $( document ).ready() block.
// $(document).ready(function () {
//     console.log("ready!");
//     // Agrega un evento de clic al enlace para limpiar el filtro de búsqueda
//     $('body').on('click', '.table-link', function () {
//         // Limpia el filtro de búsqueda de la tabla
//         dataTable.search('').columns().search('').draw();
//     });
// });



        



function checkDates() {
    const endDate = new Date(endDateInput.value);
    const now = new Date();

    if (endDate > now) {
        extendedEndDateDiv.style.display = 'block';
    } else {
        extendedEndDateDiv.style.display = 'none';
    }

    // Deshabilitar end_date_time si la fecha actual es mayor
    endDateInput.disabled = now > endDate;

}        
