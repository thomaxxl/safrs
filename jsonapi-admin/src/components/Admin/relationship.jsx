import React from 'react';
import { connect } from 'react-redux'
import * as analyzejson from './analyzejson'
import { bindActionCreators } from 'redux'
import {
  Header,
  Grid,
  List,
  Form,
  Button,
  Input,
  Select,
} from 'semantic-ui-react'

var styleheight2 = {
  minHeight:"295px",
}

var stylefloat = {
  // float: "left",
  marginTop: "10px",
  width: "55%"
}

var stylefloat1 = {
  float: "right",
  marginTop: "10px",
  width: "55%"
}

var styleboder = {
  border: "solid 1px",
  color: "rgb(229, 229, 229)"
}

var styleconlabel = {
  marginTop: "10px"
}

var stylelabel = {
  color: "black",
  backgroundColor: "#e8e8e8",
  padding: "10px",
  width: "44%"
}

var rstylelabel = {
  color: "black",
  backgroundColor: "#9fa5aa",
  padding: "10px",
  width: "44%"
}

var styleselect = {
  width: "55%"
}

let backstyle = {
  backgroundColor: "#e5e5e5"
}

class Relationship extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      selected: 0,
      collecitonkey: 0,
      fields: ['text', 'dataField', 'relation_url', 'type', 'formatter', 'relationship', 'editorRenderer'],
      text: '',
      dataField: '',
      relation_url: '',
      type: '',
      formatter: '',
      relationship: '',
      editorRenderer: '',
      optionformatter:[
        {key: 1, value: 'toManyFormatter', text: 'toManyFormatter'},
        {key: 2, value: 'toOneFormatter', text: 'toOneFormatter'}
      ],
      optioneditor: [
        {key: 3, value: 'toOneEditor', text: 'toOneEditor'},
        {key: 4, value: 'ToManyRelationshipEditor', text: 'ToManyRelationshipEditor'}
      ]
    }
    this.handleOnchange = this.handleOnchange.bind(this)
    this.handleformsubmit = this.handleformsubmit.bind(this)
  }

  handleselect(index) {
    this.state.fields.map((key, index) => {
      this.state[key] = ''
      return true
    })
    this.setState({
      selected: index
    })
  }

  handleOnchange(e) {
    this.state[e.target.placeholder] = e.target.value
    const value = e.target.value
    this.setState({place: value})
  }

  getcollectionname(key_index) {
    let rlt = ''
    Object.keys(this.props.json).map(function(key, index) {
      if (index === key_index) {
        rlt = key
      }
      return true
    })
    return rlt
  }

  getattributesname(key_index) {
    let rlt = ''
    Object.keys(this.props.json).map(function(key, index) {
      if (index === this.props.index) {
        rlt = this.props.json[key]['relationship'][key_index]
      }
      return true
    }, this)
    return rlt
  }

  handleformsubmit(e) {
    e.preventDefault()
    let data = {
      collectionId: this.getcollectionname(this.props.index),
      attributesId: this.getattributesname(this.state.selected),
      text: this.state.text,
      dataField: this.state.dataField,
      relation_url: this.state.relation_url,
      type: this.state.type,
      formatter: this.state.formatter,
      relationship: this.state.relationship,
      editorRenderer: this.state.editorRenderer
    }
    this.props.analyze.change_relationship(data)
    
  }
  selecthandleOnchange(item, value) {
    this.state[item] = value
    this.setState({item: value})
  }
  
  componentWillMount() {
  }

  render() {
    let KEY = ''
    let attr = []
    let formdata = []
    let optionrelation = []
    if (this.state.collecitonkey !== this.props.index) {
      this.state.collecitonkey = this.props.index
      this.state.fields.map((key, index) => {
        this.state[key] = ''
        return true
      })
      this.state.selected = 0
    }
    if (Object.keys(this.props.json).length !== 0) {
      Object.keys(this.props.json).map(function(okey, index) {
        if (index === this.props.index) {
          KEY = okey
        }
        let data = {
          key: index,
          value: okey,
          text: okey,
        }
        optionrelation.push(data)
        return true
      },this)
      attr = this.props.json[KEY]['relationship']
      const val = this.props.json[KEY]['relationship'][this.state.selected]
      formdata = this.props.json[KEY]['relationship'][val]
      if (formdata !== undefined) {
        Object.keys(formdata).map(function(key, index) {
          if (this.state[key] === '') this.state[key] = formdata[key]
          return true
        },this)
      }
    }
    return (
      <div>
        <Header as='h4'>Relationships</Header>
        <Grid divided style={styleboder}>
          <Grid.Column width={6} style={styleheight2}>
            <List divided selection>
              {
                attr.map((Item, index) => {
                  let cons = {}
                  if (index === this.state.selected) cons = backstyle
                  return(
                    <List.Item key={index} value='index' style={cons} onClick={() => this.handleselect(index)}>
                      <List.Content>{Item}</List.Content>
                    </List.Item>
                  )
                })
              }
              </List>
          </Grid.Column>
          <Grid.Column width={10}>
            <Form widths='equal' onSubmit={this.handleformsubmit}>
              {this.state.fields.map((item, index) => {
                if (item === 'editorRenderer') {
                  return (
                    <div key={index} style={styleconlabel}>
                      <label style={stylelabel}>{item}</label>
                      <Select value={this.state[item]} onChange={(e, { value })  => this.selecthandleOnchange(item, value)} style={styleselect} placeholder='editorRenderer' options={this.state.optioneditor} />
                    </div>
                  )
                }
                if (item === 'formatter') {
                  return (
                    <div key={index} style={styleconlabel}>
                      <label style={stylelabel}>{item}</label>
                      <Select value={this.state[item]} onChange={(e, { value })  => this.selecthandleOnchange(item, value)} style={styleselect} placeholder='formatter' options={this.state.optionformatter} />
                    </div>
                  )
                }
                if (item === 'relationship') {
                  return (
                    <div key={index} style={styleconlabel}>
                      <label style={rstylelabel}>{item}{'(required)'}</label>
                      <Select value={this.state[item]} onChange={(e, { value })  => this.selecthandleOnchange(item, value)} style={styleselect} placeholder="relationship" options={optionrelation}/>
                    </div>
                  )
                }
                return(
                  <div key={index}>
                    <Input 
                      label={item}
                      style={stylefloat}
                      placeholder={item}
                      value={this.state[item]}
                      onChange={this.handleOnchange}
                    />
                  </div>
                )
              })}
              <Button disabled={Object.keys(this.props.json).length !== 0?false:true} type='submit' style={stylefloat1}>Change config</Button>
            </Form>
          </Grid.Column>
        </Grid>
      </div>
    )
  }
}

const mapStateToProps = (state) => ({
  json: state.configReducer
})

const mapDispatchToProps = dispatch => ({
  analyze: bindActionCreators(analyzejson, dispatch)
})

export default connect(mapStateToProps, mapDispatchToProps)(Relationship)


