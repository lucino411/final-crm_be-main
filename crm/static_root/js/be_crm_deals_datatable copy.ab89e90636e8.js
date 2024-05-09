let dataTable;
let dataTableIsInitialized = false;
let dataOption;

const dataTableOptions = {
    columnDefs: [
        { className: 'centered', targets: [0, 1, 2, 3, 4, 5, 6, 7, 8] },
        { orderable: false, targets: [0, 1, 2, 5, 8] },
        { searchable: false, targets: [0, 1] },
    ],
    pageLength: 10,
    destroy: true,
    // dom: 'Bfrtip',
    dom: 'QBfrtip',

    initComplete: function () {
        let api = this.api();

        api.columns([4, 8]).every(function () {
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

        // Hace un filtro al hacer clic sobre cualquier campo, menos en la columna 0
        api.on('click', 'tbody td', function (e) {
            let columnIndex = api.cell(this).index().column;

            // Si el índice de la columna es diferente de 0, realiza la búsqueda
            if (columnIndex !== 0) {
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

    await listDeals();

    dataTable = $("#datatable-deals").DataTable({
        ...dataTableOptions,
        select: true  // Agrega esta línea dentro de las opciones
    });

    dataTableIsInitialized = true;
};


const listDeals = async () => {
    try {
        const dealListElement = document.getElementById('deal-list');
        console.log(dealListElement);
        const organizationSlug = dealListElement.dataset.organizationSlug;
        const response = await fetch(`${BASE_URL}/${organizationSlug}/deal/deals_json`);
        const data = await response.json();
        console.log(response);
        let content = ``;
        
        data.deals.forEach((deal, index) => {
            const dealData = deal;
            

            console.log(dealData); // Agrega esta línea para imprimir dealData en la consola
            const createdTime = new Date(dealData.created_time).toLocaleString('es', { day: 'numeric', month: 'short', year: 'numeric' });
            // const modifiedTime = new Date(dealData.modified_time).toLocaleString('es', { day: 'numeric', month: 'short', year: 'numeric' });

            content += `
        <tr>
            <td>${dealData.first_name}</td>
            <td>${dealData.last_name}</td>
            <td>${dealData.primary_email}</td>
            <td>${dealData.country}</td>
            <td>${createdTime}</td> 
            <td>${dealData.last_modified_by}</td> 
            <td>${dealData.assigned_to}</td>
            <td>${dealData.organization__name}</td>      
        </tr>
        `;
        });
        tableBody_deals.innerHTML = content;
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




