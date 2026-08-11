$(document).ready(function() {

    $('.sortable-header').on('click', function() {
        const $header = $(this);
        const sortType = $header.data('sort');
        const dataType = $header.data('type');

        const currentDirection = $header.data('direction') || 'asc';
        const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';

        $header.data('direction', newDirection);

        let $tbody, $rows, columnIndex;

        if ($('#sale-orders-tbody').length > 0) {
            $tbody = $('#sale-orders-tbody');
            $rows = $tbody.find('tr.sale-order-row');

            switch(sortType) {
                case 'name': columnIndex = 0; break;
                case 'date_order': columnIndex = 1; break;
                case 'subject': columnIndex = 2; break;
                case 'department': columnIndex = 3; break;
                case 'ticket_type': columnIndex = 4; break;
                case 'status': columnIndex = 5; break;
                default: columnIndex = 0;
            }
        } else if ($('#products-tbody').length > 0) {
            $tbody = $('#products-tbody');
            $rows = $tbody.find('tr.product-row');

            switch(sortType) {
                case 'product_id': columnIndex = 0; break;
                case 'product_name': columnIndex = 1; break;
                case 'series_number': columnIndex = 2; break;
                case 'create_date': columnIndex = 3; break;
                case 'warranty_status': columnIndex = 4; break;
                default: columnIndex = 0;
            }
        } else if ($('#tickets-tbody').length > 0) {
            $tbody = $('#tickets-tbody');
            $rows = $tbody.find('tr.ticket-row');
            switch(sortType) {
                case 'ticket': columnIndex = 0; break;
                case 'create_date': columnIndex = 4; break;
                case 'status': columnIndex = 6; break;
                default: columnIndex = 0;
            }
        } else if ($('#files-tbody').length > 0) {
            $tbody = $('#files-tbody');
            $rows = $tbody.find('tr.file-row');

            switch(sortType) {
                case 'name': columnIndex = 0; break;
                case 'category': columnIndex = 1; break;
                case 'modification_date': columnIndex = 2; break;
                case 'size': columnIndex = 3; break;
                default: columnIndex = 0;
            }
        } else {
            return;
        }

        let rowsArray = $rows.toArray();

        rowsArray.sort(function(rowA, rowB) {
            const cellA = $(rowA).find('td').eq(columnIndex);
            const cellB = $(rowB).find('td').eq(columnIndex);
            let valueA = cellA.text().trim();
            let valueB = cellB.text().trim();

            if (dataType === 'date') {
                valueA = parseDate(valueA);
                valueB = parseDate(valueB);
            } else if (dataType === 'size') {
                valueA = parseFileSize(cellA);
                valueB = parseFileSize(cellB);
            } else {
                valueA = valueA.toLowerCase();
                valueB = valueB.toLowerCase();
            }

            if (valueA < valueB) {
                return newDirection === 'asc' ? -1 : 1;
            }
            if (valueA > valueB) {
                return newDirection === 'asc' ? 1 : -1;
            }
            return 0;
        });

        $tbody.fadeOut(150, function() {
            $tbody.empty();
            $(rowsArray).each(function() {
                $tbody.append(this);
            });
            $tbody.fadeIn(150);
        });

        updateSortIndicators($header, newDirection);
    });

    function parseDate(dateStr) {
        let date = new Date(dateStr);

        if (isNaN(date.getTime())) {
            const parts = dateStr.split('/');
            if (parts.length === 3) {
                date = new Date(parts[2], parts[1] - 1, parts[0]);
            }
        }

        if (isNaN(date.getTime())) {
            const parts = dateStr.split('-');
            if (parts.length === 3) {
                date = new Date(parts[2], parts[1] - 1, parts[0]);
            }
        }

        return isNaN(date.getTime()) ? 0 : date.getTime();
    }

    function parseFileSize($cell) {
        const sizeInBytes = $cell.attr('data-sort-size');
        if (sizeInBytes && !isNaN(sizeInBytes)) {
            return parseInt(sizeInBytes);
        }
        const sizeText = $cell.text().trim();
        const sizeMatch = sizeText.match(/^([\d.]+)\s*(B|KB|MB|GB|TB)?$/i);

        if (!sizeMatch) {
            return 0;
        }

        const value = parseFloat(sizeMatch[1]);
        const unit = (sizeMatch[2] || 'B').toUpperCase();

        const multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 * 1024,
            'GB': 1024 * 1024 * 1024,
            'TB': 1024 * 1024 * 1024 * 1024
        };

        return value * (multipliers[unit] || 1);
    }

    function updateSortIndicators($activeHeader, direction) {
        // Reset all headers
        $('.sortable-header').removeClass('active-sort');
        $('.sort-icon').removeClass('fa-sort-up fa-sort-down').addClass('fa-sort');

        $activeHeader.addClass('active-sort');
        const $icon = $activeHeader.find('.sort-icon');
        $icon.removeClass('fa-sort');

        if (direction === 'asc') {
            $icon.addClass('fa-sort-up');
        } else {
            $icon.addClass('fa-sort-down');
        }
    }

    $('.sortable-header').hover(
        function() {
            $(this).addClass('hover');
        },
        function() {
            $(this).removeClass('hover');
        }
    );

});

$(document).ready(function() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('message') === 'ticket_created') {
        $('#ticketSuccessModal').modal('show');
        const autoCloseTimer = setTimeout(function() {
            $('#ticketSuccessModal').modal('hide');
        }, 3000);
        $('#ticketSuccessModal').on('click', function() {
            clearTimeout(autoCloseTimer);
        });
        const newUrl = window.location.pathname;
        window.history.replaceState({}, '', newUrl);
    }
});