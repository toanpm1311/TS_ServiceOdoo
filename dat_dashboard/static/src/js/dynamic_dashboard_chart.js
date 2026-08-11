/** @odoo-module **/
import { loadJS } from "@web/core/assets";
import { getColor } from "@web/core/colors/colors";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
const { Component, xml, onWillStart,useState, useRef, onMounted } = owl;

export class DynamicDashboardChart extends Component {
  // Setup function of the class DynamicDashboardChart
  setup() {
    this.doAction = this.props.doAction.doAction;
    this.chartRef = useRef("chart");
    this.dialog = this.props.dialog;
    this.state = useState({ showLine: true });
    onWillStart(async () => {
      await loadJS("/dat_dashboard/static/library/js/highcharts.js");
      await loadJS("/dat_dashboard/static/library/js/exporting.js");
      await loadJS("/dat_dashboard/static/library/js/export-data.js");
      await loadJS("/dat_dashboard/static/library/js/accessibility.js");
    });
    onMounted(() => {
      const allWidgets = document.querySelectorAll('.resize-drag');
      if (allWidgets.length === 1) {
        const widget = allWidgets[0];
        this.props.widget.translate_x = "0px";
        this.props.widget.translate_y = "0px";
        this.props.widget.data_x = null;
        this.props.widget.data_y = null;
      }

      this.renderChart();
    });
  }
  // Function to export the chart in pdf, image, xlsx and csv format
  exportItem(ev) {
  ev.stopPropagation();
  ev.preventDefault();

  const type = ev.currentTarget.getAttribute("data-type");
  const chartEl = this.chartRef.el;
  const chart = Highcharts.charts.find(c => c && c.renderTo === chartEl);

  if (!chart) {
    console.error("Chart not found");
    return;
  }

  const exportMap = {
    png: "image/png",
    pdf: "application/pdf",
    csv: "text/csv",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  };

  if (type === "png" || type === "pdf") {
    chart.exportChart({ type: exportMap[type] });
  } else if (type === "csv") {
    chart.downloadCSV();
  } else if (type === "xlsx") {
    chart.downloadXLS();
  }
}
  // Function to get the configuration of the chart
  async getConfiguration(ev) {
     var id = this.props.widget.id;
  await this.doAction({
    type: "ir.actions.act_window",
    res_model: "dashboard.block",
    res_id: id,
    view_mode: "form",
    views: [[false, "form"]],
  });
  }
  // Function to remove the chart
  async removeTile(ev) {
    ev.stopPropagation();
    ev.preventDefault();
    this.dialog.add(ConfirmationDialog, {
      title: _t("Delete Confirmation"),
      body: _t("Are you sure you want to delete this item?"),
      confirmLabel: _t("YES, I'M SURE"),
      cancelLabel: _t("NO, GO BACK"),
      confirm: async () => {
        await this.props.orm.unlink("dashboard.block", [this.props.widget.id]);
        location.reload();
      },
      cancel: () => {},
    });
  }

  onToggleLine(ev) {
    this.state.showLine = ev.target.checked;
    this.renderChart(); 
    }
  // Function to render the chart
  renderChart() {
    const {
      graph_type = "bar",
      x_axis = [],
      y_axis = [],
      measured_field = "Data",
    } = this.props.widget;

    const data = x_axis.map((key, i) => ({
      name: key,
      y: y_axis[i],
      drilldown: null
    }));

    const chartTypeMap = {
      bar: "column",
      line: "line",
      pie: "pie",
      doughnut: "pie",
    };
    const chartType = chartTypeMap[graph_type] || "column";

    Highcharts.chart(this.chartRef.el, {
      chart: {
        type: chartType,
        backgroundColor: "transparent",
      },
      title: {
        text: this.props.widget.name || null,
      },
      xAxis:
        graph_type === "bar" || graph_type === "line"
          ? {
              categories: x_axis,
              title: { text: null },
              labels: { style: { fontSize: "12px", color: "#333" } },
            }
          : undefined,
      yAxis:
        graph_type === "bar" || graph_type === "line"
          ? {
              min: 0,
              title: {
                text: measured_field,
                style: { fontSize: "12px" },
              },
              labels: { style: { fontSize: "12px", color: "#333" } },
            }
          : undefined,
      tooltip: {
        pointFormat:
          graph_type === "pie" || graph_type === "doughnut"
            ? "<b>{point.y}</b> ({point.percentage:.1f}%)"
            : "<b>{point.y}</b>",
      },
      plotOptions: {
        pie: {
            allowPointSelect: true,
            cursor: 'pointer',
            dataLabels: {
                enabled: this.state.showLine,
                format: '{point.name}: {point.percentage:.1f}%',
                distance: 20
            },
            showInLegend: true,
            innerSize: graph_type === "doughnut" ? "60%" : "0%",
        },
        column: {
          borderWidth: 0,
            dataLabels: {
          enabled: this.state.showLine,
          format: '{point.y:.1f}'
        }
        },
      },
      legend: {
        enabled: true,
        itemStyle: { fontSize: "12px" },
      },
      series: [
        {
          name: measured_field,
          colorByPoint: true,
          data: data,
        },
      ],
      credits: {
        enabled: false,
      },
      exporting: {
        enabled: true,
        buttons: {
          contextButton: {
            menuItems: [
              "downloadPNG",
              "downloadJPEG",
              "downloadPDF",
              "downloadCSV",
              "downloadXLS",
            ],
          },
        },
        chartOptions: {
            chart: {
                backgroundColor: "#ffffff",
            },
        },
      },
    });
  }
}

DynamicDashboardChart.template = xml`
  <div class="resize-drag block card"
      t-att-data-x="this.props.widget.data_x"
      t-att-data-y="this.props.widget.data_y"
      t-att-style="'height:'+this.props.widget.height+'; width:'+ this.props.widget.width+ '; transform: translate('+ this.props.widget.translate_x +', '+ this.props.widget.translate_y +');'"
      t-att-data-id="this.props.widget.id">
    <div class="card-body mt-1">
      <div class="block_edit block_setting" t-on-click="() => this.getConfiguration()">
        <i title="Configuration" class="fa fa-pencil chart-edit"/>
      </div>
      <div class="block_edit block_delete" t-on-click="removeTile">
        <i title="Delete" class="fa fa-times chart-delete"/>
      </div>
      <div class="row">
        <div class="col-md-12 chart_canvas">
          <!-- Thêm checkbox ở đây -->
          <div class="form-check mb-2">
            <input type="checkbox" class="form-check-input" t-on-click="onToggleLine" t-att-checked="this.state.showLine" id="showLineInPie"/>
            <label class="form-check-label">Hiện dữ liệu</label>
          </div>
          <div t-ref="chart"
               t-att-id="'chart-'+this.props.widget.id"
               style="width:100%; height:100%;"></div>
        </div>
      </div>
    </div>
  </div>`;

