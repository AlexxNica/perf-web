var YEAR_MSECS = 365. * 24 * 60 * 60 * 1000;
var MONTH_MSECS = 30.4 * 24 * 60 * 60 * 1000;
var WEEK_MSECS = 7. * 24 * 60 * 60 * 1000;
var DAY_MSECS = 24. * 60 * 60 * 1000;
var HOUR_MSECS = 60. * 60 * 1000;

function ValueBuffer(size) {
    this.size = size;
    this.length = 0;
    this.data = new Float64Array(2 * size);
}

ValueBuffer.prototype.append = function(time, value) {
    // Could implement dynamic reallocation if we needed it
    if (this.size == this.length)
        throw new Error("Buffer is full");

    this.data[2 * this.length] = time;
    this.data[2 * this.length + 1] = value;
    this.length++;
}

ValueBuffer.prototype.merge = function(other) {
    var newLength = this.length + other.length;
    var newData = new Float64Array(2 * newLength);
    var thisPos = 0;
    var otherPos = 0;
    var newPos = 0;
    var thisFloats = this.length * 2;
    var otherFloats = other.length * 2;

    while (thisPos < thisFloats || otherPos < otherFloats) {
        if (thisPos == thisFloats) {
            newData[newPos] = other.data[otherPos];
            newData[newPos + 1] = other.data[otherPos + 1];
            otherPos += 2;
        } else if (otherPos == otherFloats ||
                   this.data[thisPos] < other.data[otherPos]) {
            newData[newPos] = this.data[thisPos];
            newData[newPos + 1] = this.data[thisPos + 1];
            thisPos += 2;
        } else  {
            newData[newPos] = other.data[otherPos];
            newData[newPos + 1] = other.data[otherPos + 1];
            otherPos += 2;
        }

        newPos += 2;
    }

    this.data = newData;
    this.size = this.length = newLength;
}

function pad(n) {
    return (n < 10) ? '0' + n : '' + n;
}

var strokeStyles = [
    '#0000ff',
    '#00ff00',
    '#ff0000',
    '#008888',
    '#880088',
    '#000088'
];

function Chart(svg) {
    this.metric = svg.getAttribute('data-metric');
    this.target = svg.hasAttribute('data-target') ?
        svg.getAttribute('data-target') : null;
    this.svg = svg;

    this.title = $( svg ).find( ".chart-title" ).get(0);
    this.xLabels = $( svg ).find( ".chart-x-labels" ).get(0);
    this.yLabels = $( svg ).find( ".chart-y-labels" ).get(0);
    this.upperText = $( svg ).find( ".chart-upper" ).get(0);
    this.lowerText = $( svg ).find( ".chart-lower" ).get(0);
    this.background = $( svg ).find( ".chart-background" ).get(0);
    this.body = $( svg ).find( ".chart-body" ).get(0);

    this.top = 10;
    this.bottom = 10;
}

Chart.prototype.x = function(time) {
    return this.bodyWidth * (time - theDisplay.startSeconds) / theDisplay.rangeSeconds;
}

Chart.prototype.y = function(value) {
    return this.bodyHeight * (1 - (value - this.bottom) / (this.top - this.bottom));
}

function createElement(name, cls) {
    var element = document.createElementNS("http://www.w3.org/2000/svg", name);
    if (cls != null)
        element.setAttribute("class", cls);
    return element;
}

function allocateElement(element, x, y, width, height, isolateChildren) {
    element.setAttribute("x", x);
    element.setAttribute("y", y);
    element.setAttribute("width", width);
    element.setAttribute("height", height);
    if (isolateChildren)
        element.setAttribute("transform", "translate(" + x + ", " + y + ")");
}

function positionElement(element, x, y) {
    element.setAttribute("x", x);
    element.setAttribute("y", y);
}

var MARGIN_TOP = 15;
var MARGIN_RIGHT = 0;
var MARGIN_BOTTOM = 10;
var MARGIN_LEFT = 29;

Chart.prototype.allocate = function() {
    this.width = this.svg.parentNode.clientWidth;
    this.height = this.svg.parentNode.clientHeight;
    this.svg.setAttribute("viewBox",
                          "0 0 " + this.width + " " + this.height);

    this.bodyWidth = this.width - (MARGIN_LEFT + MARGIN_RIGHT + 2);
    this.bodyHeight = this.height - (MARGIN_TOP + MARGIN_BOTTOM + 2);

    positionElement(this.title, MARGIN_LEFT, MARGIN_TOP - 3, true);
    allocateElement(this.xLabels, MARGIN_LEFT + 1, this.height - MARGIN_BOTTOM, this.bodyWidth, MARGIN_BOTTOM, true);

    allocateElement(this.yLabels, 0,  MARGIN_TOP + 1, MARGIN_LEFT, this.bodyHeight, true);
    positionElement(this.upperText, MARGIN_LEFT - 3, 8);
    positionElement(this.lowerText, MARGIN_LEFT - 3, this.bodyHeight);

    allocateElement(this.background, MARGIN_LEFT + 1 - 0.5, MARGIN_TOP + 1 - 0.5, this.bodyWidth + 1, this.bodyHeight + 1);
    allocateElement(this.body,       MARGIN_LEFT + 1,       MARGIN_TOP + 1,       this.bodyWidth,     this.bodyHeight);
}

Chart.prototype.drawTarget = function(targetData) {
    var values = targetData.values;
    var index = targetData.index;

    if (values.length == 0)
        return;

    path = "";
    for (var i = 0; i < 2 * values.length; i += 2)
        path += this.x(values.data[i]) + "," + this.y(values.data[i + 1]) + " ";

    var polyline = createElement("polyline");
    polyline.setAttribute("stroke", strokeStyles[index % strokeStyles.length]);
    polyline.setAttribute("fill", "none");
    polyline.setAttribute("points", path);
    this.body.appendChild(polyline);

    for (var i = 0; i < 2 * values.length; i += 2) {
        var x = this.x(values.data[i]);
        var y = this.y(values.data[i + 1]);

        var rect = createElement("rect");
        allocateElement(rect, x - 2, y - 2, 4, 4);
        rect.setAttribute("fill", strokeStyles[index % strokeStyles.length]);
        this.body.appendChild(rect);
    }
}

Chart.prototype.getTargets = function() {
    var targets = [];

    for (var i = 0; i < theDisplay.allTargetsSorted.length; i++) {
        var target = theDisplay.allTargetsSorted[i];
        if (this.target && target != this.target)
            continue;
        if (!(target in theDisplay.data[this.metric]))
            continue;

        targets.push({
            index: i,
            target: target,
            values: theDisplay.data[this.metric][target]
        });
    }

    return targets;
}

TIME_OPS = {
    month3: {
        truncate: function(date) {
            date.setUTCDate(0);
            date.setUTCHours(0);
            date.setUTCMinutes(0);
            date.setUTCSeconds(0);
            date.setUTCMilliseconds(0);
            date.setTime(date.getTime() - (date.getUTCMonth() % 3) * MONTH_MSECS);
        },
        next: function(date) {
            var months = date.getUTCMonth();
            if (months == 9) {
                date.setUTCMonth(0);
                date.setUTCFullYear(date.getUTCFullYear() + 1);
            } else {
                date.setUTCMonth(months + 3);
            }
        },
        format: function(date) {
            return date.getUTCFullYear() + '-' + pad(date.getUTCMonth() + 1);
        }
    },
    month: {
        truncate: function(date) {
            date.setUTCDate(0);
            date.setUTCHours(0);
            date.setUTCMinutes(0);
            date.setUTCSeconds(0);
            date.setUTCMilliseconds(0);
        },
        next: function(date) {
            var months = date.getUTCMonth();
            if (months == 11) {
                date.setUTCMonth(0);
                date.setUTCFullYear(date.getUTCFullYear() + 1);
            } else {
                date.setUTCMonth(months + 1);
            }
        },
        format: function(date) {
            return date.getUTCFullYear() + '-' + pad(date.getUTCMonth() + 1);
        }
    },
    week: {
        truncate: function(date) {
            date.setUTCHours(0);
            date.setUTCMinutes(0);
            date.setUTCSeconds(0);
            date.setUTCMilliseconds(0);
            date.setTime(date.getTime() - ((date.getUTCDay() + 6) % 7) * DAY_MSECS);
        },
        next: function(date) {
            date.setTime(date.getTime() + WEEK_MSECS);
        },
        format: function(date) {
            return date.getUTCFullYear() + '-' + pad(date.getUTCMonth() + 1) + '-' + pad(date.getUTCDate());
        }
    },
    day: {
        truncate: function(date) {
            date.setUTCHours(0);
            date.setUTCMinutes(0);
            date.setUTCSeconds(0);
            date.setUTCMilliseconds(0);
        },
        next: function(date) {
            date.setTime(date.getTime() + DAY_MSECS);
        },
        format: function(date) {
            return (date.getUTCMonth() + 1) + '-' + pad(date.getUTCDate());
        }
    },
    hour6: {
        truncate: function(date) {
            date.setUTCMinutes(0);
            date.setUTCSeconds(0);
            date.setUTCMilliseconds(0);
            date.setTime(date.getTime() - (date.getUTCHours() % 6) * HOUR_MSECS);
        },
        next: function(date) {
            date.setTime(date.getTime() + 6 * HOUR_MSECS);
        },
        format: function(date) {
            return (date.getUTCMonth() + 1) + '-' + pad(date.getUTCDate()) + ' ' + pad(date.getUTCHours()) + ":00";
        }
    },
    hour: {
        truncate: function(date) {
            date.setUTCMinutes(0);
            date.setUTCSeconds(0);
            date.setUTCMilliseconds(0);
        },
        next: function(date) {
            date.setTime(date.getTime() + HOUR_MSECS);
        },
        format: function(date) {
            return (date.getUTCMonth() + 1) + '-' + pad(date.getUTCDate()) + ' ' + pad(date.getUTCHours()) + ":00";
        }
    }
};

Chart.prototype.drawXLabels = function() {
    $( this.xLabels ).empty();

    var truncate;
    var step;
    var format;

    var msecs_per_step = 1000 * theDisplay.rangeSeconds / (this.width / 50);

    var timeOps;
    if (msecs_per_step > MONTH_MSECS) {
        timeOps = TIME_OPS.month3;
    } else if (msecs_per_step > WEEK_MSECS) {
        timeOps = TIME_OPS.month;
    } else if (msecs_per_step > DAY_MSECS) {
        timeOps = TIME_OPS.week;
    } else if (msecs_per_step > 6 * HOUR_MSECS) {
        timeOps = TIME_OPS.day;
    } else if (msecs_per_step > HOUR_MSECS) {
        timeOps = TIME_OPS.hour6;
    } else {
        timeOps = TIME_OPS.hour;
    }

    var startTime = theDisplay.startSeconds * 1000;
    var endTime = theDisplay.endSeconds * 1000;

    var date = new Date(startTime);
    timeOps.truncate(date);
    while (date.getTime() < endTime) {
        if (date.getTime() >= startTime) {
            var x = this.x(date.getTime() / 1000);
            var t = createElement("text", "chart-xlabel");
            positionElement(t, x, 10);
            t.appendChild(document.createTextNode(timeOps.format(date)));
            this.xLabels.appendChild(t);

            var rect = createElement("rect", "chart-grid");
            allocateElement(rect, x - 0.5, 0, 1, this.bodyHeight);
            this.body.appendChild(rect);
        }
        timeOps.next(date);
    }
}

Chart.prototype.drawYLabels = function(targets) {
    // Always include the X-axis
    var bottom = 0;
    var top = 0;

    for (var i = 0; i < targets.length; i++) {
        var targetData = targets[i];
        var values = targetData.values;

        for (var j = 0; j < 2 * values.length; j += 2) {
            var time = values.data[j];
            var value = values.data[j + 1];

            if (time > theDisplay.startSeconds && time < theDisplay.endSeconds) {
                bottom = Math.min(value, bottom);
                top = Math.max(value, top);
            }
        }
    }

    // We want to find a multiple of 2, 5, or 10 that covers the range
    // bottom to top in about 5 steps
    var step;
    var steps;

    if (bottom == 0 && top == 0) {
        step = 2;
        steps = 5;
        top = 10;
    } else {
        var bottomBase = 0;
        var topBase = 0;

        if (bottom < 0)
            bottomBase = Math.pow(10, Math.ceil(Math.log10(-bottom)));

        if (top > 0)
            topBase = Math.pow(10, Math.ceil(Math.log(top) / Math.LN10));

        var base = Math.max(bottomBase, topBase);

        function calcSteps(step) {
            return Math.ceil(top / step) + Math.ceil(-bottom / step);
        }

        step = s = base;
        while (calcSteps(s) <= 10) {
            if (Math.abs(calcSteps(s) - 5) < Math.abs(calcSteps(step) - 5))
                step = s;
            if (Math.abs(calcSteps(s / 2) - 5) < Math.abs(calcSteps(step) - 5))
                step = s / 2;
            if (Math.abs(calcSteps(s / 5) - 5) < Math.abs(calcSteps(step) - 5))
                step = s / 5;

            s /= 10;
        }

        top = step * Math.ceil(top / step);
        bottom = - step * Math.ceil(-bottom / step);
        steps = calcSteps(step);
    }

    var displayTop = top;
    var displayBottom = bottom;

    units = this.svg.getAttribute('data-metric-units');
    if (units == 's' || units == 'ms' || units == 'us') {
        if (units == 's') {
            displayTop *= 1000000;
            displayBottom *= 1000000;
        } else if (units == 'ms') {
            displayTop *= 1000;
            displayBottom *= 1000;
        }

        if (bottom <= -1000000 || top >= 1000000) {
            displayTop /= 1000000;
            displayBottom /= 1000000;
        } else if (bottom <= -100 || top >= 1000) {
            displayTop /= 1000;
            displayBottom /= 1000;
        }
    }

    $( this.upperText ).empty();
    this.upperText.appendChild(document.createTextNode(displayTop));
    $( this.lowerText ).empty();
    this.lowerText.appendChild(document.createTextNode(displayBottom));

    this.bottom = bottom;
    this.top = top;

    for (i = 1; i < steps; i++) {
        var rect = createElement("rect", "chart-grid");
        allocateElement(rect, 0, this.y(bottom + i * step) - 0.5, this.bodyWidth, 1);
        this.body.appendChild(rect);
    }
}

Chart.prototype.draw = function() {
    this.allocate();

    $( this.body ).empty();

    this.drawXLabels();

    if (!(this.metric in theDisplay.data))
        return;

    targets = this.getTargets();

    this.drawYLabels(targets);

    for (var i = 0; i < targets.length; i++)
        this.drawTarget(targets[i]);
}

////////////////////////////////////////////////////////////////////////

function TableColumn(values) {
    this.values = values;
    this.position = 0;
}

TableColumn.prototype.prepareRange = function(min, max, units) {
    var multiplier = 1;
    if (units == 'ms') {
        multiplier = 1000;
        units = 'us';
    } else if (units == 's') {
        multiplier = 1000000;
        units = 'us';
    }

    var absMax = multiplier * Math.max(Math.abs(min), Math.abs(max));
    if (units == 'us') {
        if (absMax >= 1000000) {
            multiplier /= 1000000;
            absMax /= 1000000;
            units = 's';
        } else if (absMax >= 1000) {
            multiplier /= 1000;
            absMax /= 1000;
            units = 'ms';
        }
    }

    var range = multiplier * (max - min);

    // Determine how many digits we need to avoid scientific notation
    var digits
    if (absMax == 0) {
        digits = 1;
    } else {
        digits = 1 + Math.floor(Math.log(absMax) / Math.LN10);
        // TWEAKABLE: minimum number of displayed significant digits
        digits = Math.max(digits, 3)
        // TWEAKABLE: maximum number of displayed significant digits
        digits = Math.min(digits, 6)

        // Determine how many digits we need to distinguish the values
        if (range > 0) {
            var rangeDigits = 1 + Math.floor(Math.log(absMax) / Math.LN10) - Math.floor(Math.log(range) / Math.LN10);
            digits = Math.max(digits, rangeDigits)
        }
    }

    this.units = units;
    this.formatFunction = function(n) {
        return (n * multiplier).toPrecision(digits);
    };
}

////////////////////////////////////////////////////////////////////////

function Table(element) {
    if (element == null) // prototype
        return;

    this.table = element;
    this.target = element.getAttribute("data-target");
    this.head = $( element ).find( "thead" );
    this.body = $( element ).find( "tbody" );
    this.labelBody = $( "#rowLabelTable" ).find( "tbody" );
    this.rows = [];
    this.startTime = null;
    this.endTime = null;
    this.group = null;

    $( "#dataTableDiv" ).scroll(function() {
        $( "#columnLabelTable" ).css("left", - $( this ).scrollLeft() + "px");
        $( "#rowLabelTable" ).css("top", - $( this ).scrollTop() + "px");
    });
}

Table.prototype.refresh = function() {
    var startTime = theDisplay.startSeconds;
    var endTime = theDisplay.endSeconds;

    if (this.group != theDisplay.loadedGroup) {
        $( this.body ).empty();
        $( this.labelBody ).empty();
        this.startTime = null;
        this.endTime = null;
    } else {
        if (this.startTime != null) {
            this.startTime = Math.max(this.startTime, startTime);
            this.endTime = Math.min(this.endTime, endTime);
            if (this.startTime >= this.endTime) {
                this.startTime = null;
                this.endTime = null;
            }
        }

        $( this.body ).find("tr").each(function() {
            if (this.__time < startTime || this.__time > endTime) {
                this.parentNode.removeChild(this);
            }
        });
        $( this.labelBody ).find("tr").each(function() {
            if (this.__time < startTime || this.__time > endTime)
                this.parentNode.removeChild(this);
        });

    }

    var columns = this.prepareColumns();
    var lastInserted = null;
    var lastInsertedLabel = null;

    while (true) {
        var firstTime = null;
        for (var i = 0; i < columns.length; i++) {
            var column = columns[i];
            if (column != null && column.position < column.values.length) {
                var time = column.values.data[2 * column.position]
                if (firstTime == null || time < firstTime)
                    firstTime = time;
            }
        }

        if (firstTime == null)
            break;

        var prepend = false, append = false;
        if (firstTime >= startTime && firstTime < endTime) {
            if (this.startTime != null) {
                if (firstTime < this.startTime)
                    prepend = true;
                else if (firstTime >= this.endTime)
                    append = true;
            } else {
                append = true;
            }
        }

        var row;
        if (append || prepend) {
            var row = $( '<tr />' );
            row.get(0).__time = firstTime;

            var date = new Date(firstTime * 1000);
            var timeText;
            if (theDisplay.loadedGroup == 'week' || theDisplay.loadedGroup == 'day')
                timeText = ((date.getUTCMonth() + 1) + '-' + date.getUTCDate() + ' ');
            else
                timeText = ((date.getUTCMonth() + 1) + '-' + date.getUTCDate() + ' ' +
                            date.getUTCHours() + ':' + pad(date.getUTCMinutes()));
            $( '<th />' ).attr('class', 'row-label').text(timeText).appendTo(row);

            var labelRow = $( '<tr />' );
            labelRow.get(0).__time = firstTime;
            $( '<th />' ).attr('class', 'row-label').text(timeText).appendTo(labelRow);

            for (var i = 0; i < columns.length; i++) {
                var column = columns[i];

                if (column == null || column.position == column.values.length)
                {
                    $( '<td />' ).appendTo(row);
                    continue;
                }

                var time = column.values.data[2 * column.position];
                if (time != firstTime)
                {
                    $( '<td />' ).appendTo(row);
                    continue;
                }

                var value = column.values.data[2 * column.position + 1];

                $( '<td />' ).text(column.formatFunction(value)).appendTo(row);
                column.position++;
            }
        } else {
            for (var i = 0; i < columns.length; i++) {
                var column = columns[i];
                if (column != null) {
                    var time = column.values.data[2 * column.position];
                    if (time == firstTime)
                        column.position++;
                }
            }
        }

        if (prepend) {
            if (lastInserted == null) {
                row.prependTo(this.body);
                labelRow.prependTo(this.labelBody);
            } else {
                row.insertAfter(lastInserted);
                labelRow.insertAfter(lastInsertedLabel);
            }
            lastInserted = row;
            lastInsertedLabel = labelRow;
        } else if (append) {
            row.appendTo(this.body);
            labelRow.appendTo(this.labelBody);
        }

    }

    this.group = theDisplay.loadedGroup;
    this.startTime = startTime;
    this.endTime = endTime;
};

////////////////////////////////////////////////////////////////////////

function MetricTable(element) {
    Table.call(this, element);
}

MetricTable.prototype = new Table();

MetricTable.prototype.prepareColumns = function() {
    var columns = [];

    this.head.find( "th" ).each(function(index, element) {
        if (!element.hasAttribute('data-metric'))
            return;

        var metric = element.getAttribute('data-metric');
        var units = element.getAttribute('data-metric-units');
        if ((metric in theDisplay.data) &&
            (this.target in theDisplay.data[metric]) &&
            theDisplay.data[metric][this.target].length > 0)
        {
            var values = theDisplay.data[metric][this.target];
            var min, max;
            min = max = values.data[1];
            for (var i = 1; i < values.length; i++) {
                var value = values.data[2 * i + 1];
                min = Math.min(min, value);
                max = Math.max(max, value);
            }

            var column = new TableColumn(values);
            column.prepareRange(min, max, units);
            units = column.units;
            columns.push(column);

        } else {
            columns.push(null);
        }
        $( 'thead [data-metric="' + metric + '"] .metric-unit' ).text(units);
    }.bind(this));

    return columns;
}

////////////////////////////////////////////////////////////////////////

function TargetTable(element) {
    Table.call(this, element);
}

TargetTable.prototype = new Table();

TargetTable.prototype.prepareColumns = function() {
    var min, max;

    var metric = this.table.getAttribute('data-metric');
    var units = this.table.getAttribute('data-metric-units');
    var metricData = (metric in theDisplay.data) ? theDisplay.data[metric] : null;

    if (metricData != null) {
        this.head.find( "th" ).each(function(index, element) {
            if (!element.hasAttribute('data-target'))
                return;

            var target = element.getAttribute('data-target');
            if (target in metricData) {
                var values = metricData[target];
                for (var i = 0; i < values.length; i++) {
                    var value = values.data[2 * i + 1];
                    if (min == null) {
                        min = max = value;
                    } else {
                        min = Math.min(min, value);
                        max = Math.max(max, value);
                    }
                }
            }
        });
    }

    var columns = [];

    var displayUnits;
    this.head.find( "th" ).each(function(index, element) {
        if (!element.hasAttribute('data-target'))
            return;

        var target = element.getAttribute('data-target');
        if (min != null && target in metricData) {
            var values = metricData[target];
            var column = new TableColumn(values);
            column.prepareRange(min, max, units);
            displayUnits = column.units;
            columns.push(column);
        } else {
            columns.push(null);
        }
    });

    $( '#metricUnits' ).text(displayUnits);

    return columns;
}

////////////////////////////////////////////////////////////////////////
// Arithmetic on a list of half-open intervals. Simplicity of implementation
// was favored in writing this over performance
////////////////////////////////////////////////////////////////////////

function TimeRanges() {
    this.ranges = [];
}

TimeRanges.prototype.add = function(start, end) {
    this.subtract(start, end);

    var toInsert = {
        start: start,
        end: end
    };
    for (var i = 0; i < this.ranges.length; i++) {
        if (start < this.ranges[i].start) {
            this.ranges.splice(i, 0, toInsert);
            toInsert = null;
            break;
        }
    }

    if (toInsert)
        this.ranges.push(toInsert);

    for (var i = 1; i < this.ranges.length; i++) {
        if (this.ranges[i].start == this.ranges[i - 1].end) {
            this.ranges[i - 1].end = this.ranges[i].end;
            this.ranges.splice(i, 1);
            i--;
        }
    }
}

TimeRanges.prototype.addRanges = function(other) {
    for (var i = 0; i < other.ranges.length; i++)
        this.add(other.ranges[i].start, other.ranges[i].end);
}

TimeRanges.prototype.subtract = function(start, end) {
    for (var i = 0; i < this.ranges.length; i++) {
        var range = this.ranges[i];
        if (end > range.start && start < range.end) {
            if (start <= range.start) {
                range.start = Math.min(range.end, end);
                if (range.start == range.end) {
                    this.ranges.splice(i, 1);
                    i--;
                }
            } else if (end >= range.end) {
                range.end = start;
            } else {
                this.ranges.splice(i + 1, 0,
                                   {
                                       start: end,
                                       end: range.end
                                   });
                range.end = start;
                i++;
            }
        }
    }
}

TimeRanges.prototype.subtractRanges = function(other) {
    for (var i = 0; i < other.ranges.length; i++)
        this.subtract(other.ranges[i].start, other.ranges[i].end);
}

TimeRanges.prototype.isEmpty = function() {
    return this.ranges.length == 0;
}

TimeRanges.prototype.toString = function() {
    var result = '';
    for (var i = 0; i < this.ranges.length; i++) {
        if (result.length > 0)
            result += ' ';
        result += '[' + this.ranges[i].start + ',' + this.ranges[i].end + ')';
    }
    return result;
}

////////////////////////////////////////////////////////////////////////

function PerfDisplay(target, metric, dataMinTime, dataMaxTime, centerTime, rangeType) {
    this.target = target;
    this.metric = metric;
    this.dataMinTime = dataMinTime;
    this.dataMaxTime = dataMaxTime;

    this.charts = [];
    this.table = null;
    this.data = {};
    this.allTargets = {};
    this.allTargetsSorted = [];

    this.windowLoaded = false;

    this.pendingLoads = [];
    this.loadedGroup = null;
    this.loadedRanges = new TimeRanges();

    this.setPositionAndRange(centerTime, rangeType, false);
    $(window).load(this.onWindowLoaded.bind(this));
}

PerfDisplay.prototype.setPositionAndRange = function(centerTime, rangeType, clampCenter) {
    this.rangeType = rangeType;

    switch (rangeType) {
        case 'day':
           this.rangeSeconds = DAY_MSECS / 1000;
           this.group = 'none';
           break;
        case 'week':
           this.rangeSeconds = WEEK_MSECS / 1000;
           this.group = 'hour6';
           break;
        case 'month':
           this.rangeSeconds = MONTH_MSECS / 1000;
           this.group = 'day';
           break;
        case 'year':
           this.rangeSeconds = YEAR_MSECS / 1000;
           this.group = 'week';
           break;
    }

    var margin = this.rangeSeconds / 10;

    this.centerTime = centerTime;
    this.startSeconds = Math.max(this.centerTime - this.rangeSeconds / 2, this.dataMinTime - margin);
    this.endSeconds = Math.min(this.startSeconds + this.rangeSeconds, this.dataMaxTime + margin);
    this.startSeconds = this.endSeconds - this.rangeSeconds;

    if (clampCenter)
        this.centerTime = this.endSeconds - this.rangeSeconds / 2;

    this.load();
    this.refresh();
}

PerfDisplay.prototype.refresh = function() {
    if (!this.windowLoaded)
        return;

    for (var i = 0; i < this.charts.length; i++)
        this.charts[i].draw();

    if (this.table != null)
        this.table.refresh();
}

var TIME_OFFSETS = {
    'none': 0,
    'hour6': 3 * 60 * 60,
    'day': 12 * 60 * 60,
    'week': 3.5 * 24 * 60 * 60,
    'month': 15.2 * 24 * 60 * 60
}

function formatDay(date) {
    return date.getUTCFullYear() + '-' + pad(date.getUTCMonth() + 1) + '-' + pad(date.getUTCDate());
}

PerfDisplay.prototype.load = function() {
    var startSeconds = this.startSeconds;
    var endSeconds = this.endSeconds;
    var group = this.group;

    var dataMinTime = this.dataMinTime;
    var dataMaxTime = this.dataMaxTime;

    if (group != 'none') {
        var dataMinDate = new Date(dataMinTime * 1000);
        TIME_OPS[group].truncate(dataMinDate);
        dataMinTime = dataMinDate.getTime() / 1000;
        var maxDataDate = new Date(dataMaxTime * 1000);
        TIME_OPS[group].truncate(maxDataDate);
        TIME_OPS[group].next(maxDataDate);
        dataMaxTime = maxDataDate.getTime() / 1000;
    }

    // There's no point in asking for data the server doesn't have
    startSeconds = Math.max(dataMinTime, startSeconds);
    endSeconds = Math.min(dataMaxTime, endSeconds);
    if (endSeconds <= startSeconds)
        return;

    // API is in terms of days, retrieves all summaries that
    // overlap that range of days; we round our retrieved range to
    // the boundaries of the API so that the "all overlapping" doesn't
    // affect the retrieved range

    // Find the day range
    var startDate = new Date(startSeconds * 1000);
    TIME_OPS['day'].truncate(startDate);
    var endDate = new Date(endSeconds * 1000);
    TIME_OPS['day'].truncate(endDate);
    if (endDate.getTime() != endSeconds * 1000)
        TIME_OPS['day'].next(endDate);

    if (startDate.getTime() == endDate.getTime()) // Empty day range
        return;

    // Round to summary boundaries
    if (group != 'none') {
        TIME_OPS[group].truncate(startDate);
        var tmp = endDate.getTime();
        TIME_OPS[group].truncate(endDate);
        if (tmp != endDate.getTime())
            TIME_OPS[group].next(endDate);
    }

    var timeRanges = new TimeRanges();
    timeRanges.add(startDate.getTime() / 1000, endDate.getTime() / 1000);

    var i;
    var groupChanged = false;

    // Now remove data that we are loading
    for (i = this.pendingLoads.length - 1; i >= 0; i--) {
        if (this.pendingLoads[i].group != group) {
            groupChanged = true;
            break;
        }
        timeRanges.subtract(this.pendingLoads[i].start, this.pendingLoads[i].end);
    }

    // And data we already have
    if (!groupChanged && this.loadedGroup == group)
        timeRanges.subtractRanges(this.loadedRanges);

    for (var i = 0; i < timeRanges.ranges.length; i++) {
        var range = timeRanges.ranges[i];
        this._loadRange(group, range.start, range.end);
    }
}

PerfDisplay.prototype._loadRange = function(group, start, end) {
    var startDate = new Date(start * 1000);
    TIME_OPS['day'].truncate(startDate);
    var endDate = new Date(end * 1000);
    TIME_OPS['day'].truncate(endDate);

    // Make the day-range closed, as the API requires
    endDate.setTime(endDate.getTime() - DAY_MSECS);

    var url = '/api/values?start=' + formatDay(startDate) + '&end=' + formatDay(endDate) + '&group=' + group;
    if (this.target != null)
        url += '&target=' + encodeURIComponent(this.target);
    if (this.metric != null)
        url += '&metric=' + encodeURIComponent(this.metric);

    var loadInfo = {
        group: group,
        start: start,
        end: end,
    };

    this.pendingLoads.push(loadInfo);

    $.ajax({datatype: "json",
            url: url,
            success:
              function(data) {
                  var addedData = false;

                  this.pendingLoads.splice(this.pendingLoads.indexOf(loadInfo), 1);

                  var timeOffset = TIME_OFFSETS[group];

                  if (group != this.loadedGroup) {
                      this.data = {};
                      this.loadedRanges = new TimeRanges();
                      this.loadedGroup = group;
                  }

                  this.loadedRanges.add(start, end);

                  for (var i = 0; i < data.length; i++) {
                      var metricData = data[i];
                      if (!(metricData.name in this.data))
                          this.data[metricData.name] = {};

                      for (var j = 0; j < metricData.targets.length; j++) {
                          var targetData = metricData.targets[j];

                          var valuesData = targetData.values;

                          if (valuesData.length > 0)
                              addedData = true;
                          else
                              continue;

                          var values = new ValueBuffer(valuesData.length);
                          if (group == 'none') {
                              for (var k = 0; k < valuesData.length; k++) {
                                  var value = valuesData[k];
                                  values.append(value.time, value.value);
                              }
                          } else {
                              for (var k = 0; k < valuesData.length; k++) {
                                  var value = valuesData[k];
                                  values.append(value.time + timeOffset, value.avg);
                              }
                          }

                          if (targetData.name in this.data[metricData.name])
                              this.data[metricData.name][targetData.name].merge(values);
                          else
                              this.data[metricData.name][targetData.name] = values;

                          this.allTargets[targetData.name] = 1;
                      }
                  }

                  if (!addedData)
                      return;

                  this.allTargetsSorted = [];
                  for (var target in this.allTargets)
                      theDisplay.allTargetsSorted.push(target);
                  this.allTargetsSorted.sort();

                  this.refresh();
              }.bind(this),
            error:
              function() {
                  this.pendingLoads.splice(this.pendingLoads.indexOf(loadInfo), 1);
             }});
}

PerfDisplay.prototype.onWindowLoaded = function() {
    if (this.windowLoaded)
        return;

    this.windowLoaded = true;

    $( ".chart" ).each(function() {
        theDisplay.charts.push(new Chart(this));
    });

    $( "#dataTable" ).each(function() {
        if (this.hasAttribute("data-metric"))
            theDisplay.table = new TargetTable(this);
        else
            theDisplay.table = new MetricTable(this);
    });

    var mainLeft = $( "#mainLeft" ).get(0);
    mainLeft.addEventListener("wheel", function(event) {
        if (event.deltaX == 0)
            return;

        var chart = $( ".chart" ).first().get(0);
        var chartBodyWidth = chart.parentNode.clientWidth - (MARGIN_LEFT + MARGIN_RIGHT + 2);
        this.setPositionAndRange(this.centerTime + 10 * event.deltaX * this.rangeSeconds / chartBodyWidth,
                                 this.rangeType,
                                 true);
    }.bind(this));

    $( window ).resize(function() {
        this.refresh();
    }.bind(this));

    if (!this.loadedRanges.isEmpty())
        this.refresh();
}

//////////////////////////////////////////////////////////////////////////////////

function setRange(e, a, rangeType) {
    e.preventDefault();
    $( "#aboveMainLeft a" ).removeClass('range-active');
    $( a ).addClass('range-active');

    theDisplay.setPositionAndRange(theDisplay.centerTime, rangeType, false);
}

function initialize(target, metric, dataMinTime, dataMaxTime) {
    theDisplay = new PerfDisplay(target, metric, dataMinTime, dataMaxTime, Date.now() / 1000, 'week');
}
