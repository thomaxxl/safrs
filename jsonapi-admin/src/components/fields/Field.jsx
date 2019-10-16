import React from 'react';
import { FormGroup, Label, Input } from 'reactstrap';

class Field extends React.Component {  
    // constructor(){
    //     super()
    // }

    getInput(){
        let column = this.props.column
        let data = this.props.data
        let result = ''
        if(!column){
            result = <div/>
        }
        else if( data && ( column.readonly || data[column.dataField] === undefined )){
            result = data[column.dataField]
        }
        else if(column.editor){
            //result = column.editor
            //let formatter = Param.FormatterList[column.editor]
            result = 'editor TODO'
        }
        else if(column.editorRenderer){
           const EditorRenderer = column.editorRenderer
           let defaultValue= this.props.value
           result = <EditorRenderer column={column} {...this.props} defaultValue={defaultValue} onChange={this.props.onChange} />
           //result = <div>TODO</div>
           
        }
        else{
            result = <Input value={this.props.value}
                            type={column.type}
                            disabled={this.props.disabled}
                            name={column.dataField}
                            placeholder= {this.props.placeholder !== undefined && this.props.disabled === undefined? this.props.placeholder : ''}
                            onChange={this.props.onChange}/>
        }

        return <div>{result}</div>
    }

    dispatchValue(){
        /*if(column.relationship){
                                return <div>Relationship: {data[column.dataField]}</div>
                            }
                            if(column.readonly || data[column.dataField] === undefined ){
                                return <div key={index}> {data[column.dataField]} </div>
                            }    */
    }

    render(){

        var column = this.props.column;
        return <FormGroup>
                    <Label for="name" className="from-label" >{column.text}</Label>
                    {this.getInput()}
                </FormGroup>
    }
}

export default Field;