import React from 'react';
import BootstrapTable from 'react-bootstrap-table-next';
import paginationFactory from 'react-bootstrap-table2-paginator';
import 'react-bootstrap-table-next/dist/react-bootstrap-table2.min.css';
import 'react-bootstrap-table2-paginator/dist/react-bootstrap-table2-paginator.min.css';
import * as Param from '../../Config';
import cellEditFactory from 'react-bootstrap-table2-editor';
import { RingLoader } from 'react-spinners';
import { connect } from 'react-redux'


// function resolveFormatter(value){
//     return  Param.FormatterList[value.formatter]
// }

// function handleMouse(){
//     let d = ObjectApi.getAllDatas('XWConfig', 0, 1)
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

class List extends React.Component {

    constructor(props) {
        super(props)
        this.columns = []
        this.props.columns.map((value, index) => {


            /* 
                merge the config column properties 
                with our property dict
            */
            
            /* 
                Dispatch the formatter from string to function
                Only replace it the first time (when it's still a string)
                this turned out to be quite ugly... TODO: redo!
            */

            if(value.formatter){
                let formatter_name = value.formatter
                if(typeof value.formatter === 'string'){ // bah!, we only need to replace it once
                   value.formatter = Param.FormatterList[formatter_name] //resolveFormatter(value.formatter)
                }
                if (!value.formatter) { console.log(`formatter ${formatter_name} not found!`) }
            }
            if(value.editor){
                let editor_name = value.editor
                if(typeof value.editor === 'string'){
                   value.editor = Param.FormatterList[value.editor] //resolveFormatter(value.formatter)
                }
                if (!value.editor){ console.log(`formatter ${editor_name} not found!`) }   
            }

            if(value.editorRenderer && typeof value.editorRenderer === 'string'){
                const EditorRenderer = Param.FormatterList[value.editorRenderer]
                value.editorRenderer = (editorProps, value, row, column, rowIndex, columnIndex) => 
                    ( <EditorRenderer className="editable" { ...editorProps } row={row} column={column} value={ value }  /> )
            }
            if(!value.text){
                value.text = value.name
            }
            if(!value.dataField){
                console.log('No dataField for column', value)
                value.dataField = '__dummy'+Math.random(); // filler to avoid console warnings (lol if you run into this :p)
                value.readonly = true
            }
            if(value.readonly){
                value.editable = false
            }
            value.plaintext = value.text
            // let listFilter = textFilter({ className:"textFilter", 
            //                               style: { display: 'inline',
            //                                        backgroundColor: 'white', 
            //                                        visibility: 'hidden'
            //                             }})
            // const ff = <JAFilter />
            
            let column = Object.assign({}, { //filter: listFilter,
                                            delay: 100,
                                            editable : true,
                                            onSort: (field, order) => {
                                                console.log(field, order);
                                            }
                                        },
                                        value)
            this.columns.push(column);
            return 0;
        }, this);


        this.options = {
            sortIndicator: true,
            noDataText: 'No data'
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

    afterSaveCell(oldValue, newValue, row, column){
        if(column.relationship){
            this.props.handleSaveRelationship(newValue, row, column)
        }
        else{
            this.props.handleSave(row, column.dataField)
        }

        // todo!!!
    }

    render() {
        const selectRow = {
            mode: 'checkbox',
            clickToSelect: false,
            style: { backgroundColor: '#c8e6c9' },
            onSelect: this.props.handleRowSelect,
            selected: this.props.selectedIds,
            clickToEdit: true
        };

        const pager = paginationFactory({
            page: parseInt(this.props.data.offset/this.props.data.limit,10)+1,
            sizePerPage: this.props.data.limit,
            totalSize: this.props.data.count,
        });
        
            let spin = <div/>
            if (this.props.spin)
                spin =  <RingLoader
                            color={'#123abc'} 
                            loading={this.props.spin} 
                        />
            return (
                <div>
                    <BootstrapTable
                        keyField="id"
                        data={ this.props.data.data }
                        columns={ this.columns  }
                        cellEdit={ cellEditFactory({ mode: 'dbclick', afterSaveCell: this.afterSaveCell.bind(this) }) }
                        pagination={ pager }
                        selectRow={ selectRow }
                        onTableChange={this.handleTableChange.bind(this)}
                        remote={ { pagination: true } }
                    />
                    <div className='sweet-loading'>
                        {spin}
                    </div>
                </div>
                )

    }
}

const mapStateToProps = (state, own_props) => ({
    spin: state.analyzeReducer.spinner,
    select_option: state.object[own_props.objectKey].select_option
})

export default connect(mapStateToProps)(List);