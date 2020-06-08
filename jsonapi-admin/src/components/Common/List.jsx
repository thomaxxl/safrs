import React from 'react';
import BootstrapTable from 'react-bootstrap-table-next';
import paginationFactory from 'react-bootstrap-table2-paginator';
import 'react-bootstrap-table-next/dist/react-bootstrap-table2.min.css';
import 'react-bootstrap-table2-paginator/dist/react-bootstrap-table2-paginator.min.css';
import * as Param from '../../Config';
import { APP, FormatterList } from '../../Config.jsx';
import cellEditFactory from 'react-bootstrap-table2-editor';
import {connect} from 'react-redux'
import {Config} from '../../Config.jsx'
import filterFactory, { textFilter } from 'react-bootstrap-table2-filter';
import {Input} from 'reactstrap';
import {
    faCheck,
    faCheckSquare,
    faSquare,
    faMinusSquare
} from '@fortawesome/free-regular-svg-icons';
import FontAwesomeIcon from '@fortawesome/react-fontawesome';


// function resolveFormatter(value){
//     return  Param.FormatterList[value.formatter]
// }

// function handleMouse(){
//     let d = ObjectApi.getCollection('XWConfig', 0, 1)
//     d.then(data => {
//         let columns = []
//         for (let attr of Object.keys(data['XWConfig']['data'][0].attributes) ) {
//             columns.push({ "dataField" : attr })
//         }
//         console.log(JSON.stringify(columns, null, 2) )
//     })
// }

// class JAFilter extends React.Component {

//     render(){
//         let listFilter = textFilter({ className:"textFilter", 
//                                       style: { display: 'inline-block',
//                                                backgroundColor: 'yellow'
//                                     }})
//         return <div>{listFilter}</div>
//     }
// }

// class ColHeader extends React.Component {
//     // todo: this generates a warning because text is no longer a string:
//     // Warning: Failed prop type: Invalid prop `column.text` of type `object` supplied to `HeaderCell`, expected `string`.

//     onClick(){
//         alert('todo')
//     }

//     render(){
//         return  <span>{this.props.text}
//                     <FontAwesomeIcon className="column-filter" onClick={this.onClick.bind(this)} icon={faFilter} />
//                 </span>
//     }
// }

function dispatch_col_type(column){
    if(column.type === "integer"){
            let col_style = {width: '6em'}
            column.headerStyle = Object.assign({}, col_style, (column.headerStyle || {}) )
            col_style.paddingLeft = '1.5em'
            column.style = Object.assign({}, col_style, (column.style || {}) )
    }
    if(column.type === "date"){
        const col_style = {width: '12em'}
        column.style = Object.assign({}, col_style, (column.style || {}) )
        column.headerStyle = Object.assign({}, col_style, (column.headerStyle || {}) )
    }
}

let nameFilter;

const ff = textFilter({
    //placeholder: 'My Custom PlaceHolder',  // custom the input placeholder
    className: 'column-filter', // custom classname on input
    //defaultValue: 'test', // default filtering value
    //comparator: Comparator.EQ, // default is Comparator.LIKE
    caseSensitive: true, // default is false, and true will only work when comparator is LIKE
    style: { backgroundColor: 'white' }, // your custom inline styles on input
    delay: 1000, // how long will trigger filtering after user typing, default is 500 ms
    onClick: e => console.log(e),
    getFilter: (filter) => { // nameFilter was assigned once the component has been mounted.
      nameFilter = filter;
    }
  })

class List extends React.Component {

    constructor(props) {
        super(props)

        const columns = APP[this.props.objectKey].column || []

        let filtered_columns = columns.filter((col) => col.visible != false)

        this.columns = filtered_columns.map((column, index) => {
            /*
                merge the config column properties
                with our property dict
            */

            if(column.formatter){
                /*
                    Dispatch the formatter from string to function
                    Only replace it the first time (when it's still a string)
                    this turned out to be quite ugly... TODO: redo!
                */

                let formatter_name = column.formatter
                if(typeof column.formatter === 'string'){ // bah!, we only need to replace it once
                   column.formatter = FormatterList[formatter_name] //resolveFormatter(column.formatter)
                }
                if (!column.formatter){
                    console.log(`formatter ${formatter_name} not found!`)
                }
                else{
                    column.location = this.props.location
                }
            }
            if(column.headerFormatter){
                let formatter_name = column.headerFormatter
                if(typeof column.headerFormatter === 'string'){ // bah!, we only need to replace it once
                   column.headerFormatter = FormatterList[formatter_name] //resolveFormatter(column.formatter)
                }
                if (!column.headerFormatter){
                    console.log(`formatter ${formatter_name} not found!`)
                }
            }
            if(column.editor){
                let editor_name = column.editor
                if(typeof column.editor === 'string'){
                   column.editor = FormatterList[column.editor] //resolveFormatter(column.formatter)
                }
                if (!column.editor){ console.log(`formatter ${editor_name} not found!`) }
            }
            if(column.editorRenderer){
                const EditorRenderer = column.editorRenderer
                column.editorRenderer = (editorProps, value, row, column, rowIndex, columnIndex) =>
                    {   // if the route was changed , the editorProps was already rendered and contains the correct values
                        row = row ? row : editorProps.row
                        column = column ? column : editorProps.column
                        value = value ? value : editorProps.value
                        return  <EditorRenderer className="editable" { ...editorProps } row={row} column={column} value={ value }  /> 
                    }
            }
            if(!column.text){
                column.text = column.name
            }
            if(!column.dataField){
                console.log('No dataField for column', column)
                column.dataField = '__dummy'+Math.random(); // filler to avoid console warnings (lol if you run into this :p)
                column.readonly = true
            }
            if(column.readonly){
                column.editable = false
            }
            dispatch_col_type(column)

            // Customize column:
            // https://react-bootstrap-table.github.io/react-bootstrap-table2/docs/column-props.html
            //column.sort = true
            //column. headerStyle = { backgroundColor: 'green' }

            column.plaintext = column.text
            //column.filter = ff
            // let listFilter = textFilter({ className:"textFilter",
            //                               style: { display: 'inline',
            //                                        backgroundColor: 'white',
            //                                        visibility: 'hidden'
            //                             }})
            // const ff = <JAFilter />

            column = Object.assign({}, { //filter: listFilter,
                                        delay: 100,
                                        editable : true,
                                        onSort: (field, order) => {
                                            console.log(field, order);
                                        }
                                    },
                                    column)
            return column
        }, this);

        this.options = {
            sortIndicator: true,
            noDataText: 'No data',
            bgColor: '#c1f291'
        };

        this.selectRowProp = {
            mode: 'radio',
            bgColor: '#c1f291',
            onSelect: props.handleRowSelect,
            clickToSelect: true, 
            // mode: 'checkbox',  
        };
    }

    handleTableChange(type, { page, sizePerPage, filters }) {
        Object.keys(this.props.filter).map((key)=>{
            delete this.props.filter[key];
            return 0;
        })

        Object.keys(filters).map((key)=>{
            this.props.filter[key] = filters[key].filterVal;
            return 0;
        },this)

        this.props.onTableChange(page,sizePerPage);
    }

    beforeSaveCell(args){
        console.log('beforeSaveCell', args)
    }

    afterSaveCell(oldValue, newValue, row, column){
        if(column.relationship){
            this.props.handleSaveRelationship(newValue, row, column)
        }
        else{
            this.props.handleSave(row, column.dataField)
        }
    }

    render() {
        const selectionRenderer = ({ mode, checked, disabled }) => {
                    let icon = <FontAwesomeIcon icon={faSquare} />
                    if(checked){
                        icon = <FontAwesomeIcon icon={faCheckSquare} />
                    }
                    return <div className="ja-select">{icon}</div>
                }

        const selectionHeaderRenderer= ({ mode, checked, indeterminate }) => {
            let icon = <FontAwesomeIcon icon={faSquare} />
            if(indeterminate){
                icon = <FontAwesomeIcon icon={faMinusSquare} />
            }
            if(checked){
                icon = <FontAwesomeIcon icon={faCheckSquare} />
            }
            return <div className="ja-select">{icon}</div>
        }


        const selectRow = {
            mode: 'checkbox',
            clickToSelect: false,
            style: { backgroundColor: '#c8e6c9' },
            onSelect: this.props.handleRowSelect,
            selected: this.props.selectedIds,
            clickToEdit: true,
            selectionRenderer: selectionRenderer,
            selectionHeaderRenderer: selectionHeaderRenderer,
            selectColumnStyle: { backgroundColor: 'blue' },
            headerColumnStyle: { backgroundColor: 'blue' }
        }

        const customTotal = (from, to, size) => (
          <span className="react-bootstrap-table-pagination-total">
            Showing { from } to { to+1 } of { size } Results
          </span>
        )
        const limit = this.props.data.limit
        const data = this.props.data.data.slice(0,limit)
        
        const pager = paginationFactory({
            page: parseInt(this.props.data.offset/this.props.data.limit,10)+1,
            sizePerPage: limit,
            totalSize: this.props.data.count,
            paginationTotalRenderer : customTotal,
            showTotal : true,
            /*onSizePerPageChange: (sizePerPage, page) => {
                console.log('Size per page change!!!');
                console.log('Newest size per page:' + sizePerPage);
                console.log('Newest page:' + page);
                this.props.onTableChange(page,sizePerPage);
              },
            onPageChange: (page, sizePerPage) => {
                
                this.props.onTableChange(page,sizePerPage);
              }*/
        })
        
        const rowClasses = (row, rowIndex) => {
          return  rowIndex % 2 === 0 ? 't-row even-row' : 't-row  odd-row'
        }

        return <div className="ja-bootstrap-table">
                <BootstrapTable
                    rowClasses={rowClasses} 
                    keyField="id"
                    data={data}
                    columns={this.columns}
                    cellEdit={ cellEditFactory({ mode: 'dbclick', afterSaveCell: this.afterSaveCell.bind(this), beforeSaveCell : this.beforeSaveCell.bind(this) }) }
                    pagination={ pager }
                    selectRow={ selectRow }
                    onTableChange={this.handleTableChange.bind(this)}
                    filter={ filterFactory() } 
                    remote={ { pagination: true } } />
                </div>
    }
}

const mapStateToProps = (state, own_props) => ({
    spin: state.analyzeReducer.spinner,
    select_option: state.object[own_props.objectKey].select_option
})

export default connect(mapStateToProps)(List);